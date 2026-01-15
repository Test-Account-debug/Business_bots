from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.repo import create_review, list_reviews, average_rating_for_master, average_rating_for_service, get_or_create_user
import app.notify as notify_mod

router = Router()

MAX_REVIEW_TEXT = 2000


# Simple compatibility helpers for FSM state setting/getting (works with FakeState in tests)
async def _set_state(ctx, state_obj):
    try:
        await state_obj.set()
    except Exception:
        try:
            await ctx.update_data(_state=state_obj.state)
        except Exception:
            pass

async def _get_state(ctx):
    try:
        return await ctx.get_state()
    except Exception:
        data = await ctx.get_data()
        return data.get('_state')


from aiogram.fsm.state import State, StatesGroup

class ReviewStates(StatesGroup):
    RATING = State()
    TEXT = State()


@router.message(Command('leave_review'))
async def cmd_leave_review(message: Message):
    """Usage: /leave_review service_id|master_id|rating|text
    service_id or master_id can be empty (use 0) but at least one must be provided.
    rating: int 1-5
    text: optional text
    """
    args = message.get_args()
    if not args or '|' not in args:
        await message.answer('Использование: /leave_review service_id|master_id|rating|текст\nПример: /leave_review 1|2|5|Отличная стрижка!')
        return
    parts = [x.strip() for x in args.split('|', 3)]
    try:
        service_id = int(parts[0]) if parts[0] else None
    except Exception:
        await message.answer('Неверный service_id. Укажите число или оставьте пустым.')
        return
    try:
        master_id = int(parts[1]) if parts[1] else None
    except Exception:
        await message.answer('Неверный master_id. Укажите число или оставьте пустым.')
        return
    if not service_id and not master_id:
        await message.answer('Укажите хотя бы service_id или master_id. Пример: /leave_review 1||5|Хорошая услуга')
        return
    try:
        rating = int(parts[2])
        if not (1 <= rating <= 5):
            raise Exception('out of range')
    except Exception:
        await message.answer('Оценка должна быть числом от 1 до 5. Например: 4')
        return
    text = parts[3] if len(parts) > 3 else None
    if text and len(text) > MAX_REVIEW_TEXT:
        await message.answer(f'Текст отзыва слишком длинный (максимум {MAX_REVIEW_TEXT} символов). Пожалуйста, сократите.')
        return
    # ensure user exists
    user = await get_or_create_user(message.from_user.id)
    rid = await create_review(user['id'], service_id, master_id, rating, text)
    await message.answer('Спасибо за ваш отзыв! ⭐ Он поможет нам стать лучше.')
    # notify admins
    await notify_mod.notify_admins(f"Новый отзыв: id={rid} рейтинг={rating} мастер={master_id} услуга={service_id} текст={text or ''}")


@router.callback_query(lambda c: c.data and c.data.startswith('review:rating:'))
async def cb_review_rating(query, state):
    # format: review:rating:<rating>:booking:<booking_id>
    parts = query.data.split(':')
    try:
        rating = int(parts[2])
        booking_id = int(parts[4])
    except Exception:
        await query.answer('Неверные данные. Попробуйте снова.', show_alert=True)
        return
    from app.repo import get_booking, get_user_by_id
    b = await get_booking(booking_id)
    if not b:
        await query.answer('Бронирование не найдено. Обратитесь в поддержку.', show_alert=True)
        return
    if b['status'] != 'completed':
        await query.answer('Отзыв можно оставить только после завершения визита. Подождите подтверждения от мастера.', show_alert=True)
        return
    # determine DB user id
    user_db = await get_user_by_id(b['user_id'])
    if not user_db:
        await query.answer('Пользователь не найден. Обратитесь в поддержку.', show_alert=True)
        return
    rid = await create_review(user_db['id'], b['service_id'], b['master_id'], rating, None)
    try:
        await notify_mod.notify_admins(f"Новый отзыв: id={rid} рейтинг={rating} мастер={b['master_id']} услуга={b['service_id']}")
    except Exception:
        pass
    try:
        await query.message.answer('Спасибо за вашу оценку! ⭐ Если хотите, оставьте комментарий.')
    except Exception:
        pass
    await query.answer('Принято!', show_alert=False)


@router.callback_query(lambda c: c.data and c.data.startswith('review:text:booking:'))
async def cb_review_text_start(query, state):
    # starts interactive flow: ask for rating then text
    try:
        booking_id = int(query.data.split(':')[-1])
    except Exception:
        await query.answer('Неверные данные. Попробуйте снова.', show_alert=True)
        return
    await state.update_data(booking_id=booking_id)
    await _set_state(state, ReviewStates.RATING)
    await query.message.answer('Как бы вы оценили визит? Введите число от 1 до 5 ⭐\nПример: 4')
    await query.answer('Введите оценку')


@router.message(lambda message: True)
async def r_review_rating(message, state):
    cur = await _get_state(state)
    if cur != ReviewStates.RATING.state:
        return
    try:
        rating = int((message.text or '').strip())
        if rating < 1 or rating > 5:
            raise Exception()
    except Exception:
        await message.answer('Пожалуйста, введите число от 1 до 5. Например: 5')
        return
    await state.update_data(rating=rating)
    await message.answer('Расскажите подробнее (необязательно): что понравилось, что можно улучшить?')
    await _set_state(state, ReviewStates.TEXT)


@router.message(lambda message: True)
async def r_review_text(message, state):
    cur = await _get_state(state)
    if cur != ReviewStates.TEXT.state:
        return
    text = (message.text or '').strip()
    data = await state.get_data()
    rating = data.get('rating')
    booking_id = data.get('booking_id')
    from app.repo import get_booking, get_user_by_id
    b = await get_booking(booking_id)
    if not b:
        await message.answer('Бронирование не найдено')
        await state.clear()
        return
    user_db = await get_user_by_id(b['user_id'])
    if not user_db:
        await message.answer('Пользователь не найден')
        await state.clear()
        return
    rid = await create_review(user_db['id'], b['service_id'], b['master_id'], rating, text or None)
    try:
        await notify_mod.notify_admins(f"Новый отзыв: id={rid} рейтинг={rating} мастер={b['master_id']} услуга={b['service_id']} текст={text or ''}")
    except Exception:
        pass
    await message.answer('Спасибо за подробный отзыв! ⭐ Мы учтём ваши пожелания.')
    await state.clear()

@router.message(Command('list_reviews'))
async def cmd_list_reviews(message: Message):
    # admin only
    from app.handlers.admin import is_admin
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = message.get_args()
    service_id = None
    master_id = None
    if args and '|' in args:
        p = [x.strip() for x in args.split('|',1)]
        try:
            service_id = int(p[0]) if p[0] else None
            master_id = int(p[1]) if p[1] else None
        except Exception:
            await message.answer('Неверные фильтры')
            return
    rows = await list_reviews(service_id=service_id, master_id=master_id, limit=200)
    if not rows:
        await message.answer('Отзывов нет')
        return
    text = ''
    for r in rows:
        text += f"ID:{r['id']} user:{r['user_tg_id'] or 'unknown'} rating:{r['rating']} master:{r['master_id'] or ''} service:{r['service_id'] or ''} {r['text'] or ''}\n"
    await message.answer(text)

@router.message(Command('avg_rating'))
async def cmd_avg_rating(message: Message):
    args = message.get_args()
    if not args or '|' not in args:
        await message.answer('Использование: /avg_rating master|service|id — например: /avg_rating master|2')
        return
    typ, id_s = [x.strip() for x in args.split('|',1)]
    try:
        obj_id = int(id_s)
    except Exception:
        await message.answer('Неверный id')
        return
    if typ == 'master':
        avg, cnt = await average_rating_for_master(obj_id)
        await message.answer(f'Мастер {obj_id} — средняя оценка: {avg:.2f} ({cnt} отзывов)')
    elif typ == 'service':
        avg, cnt = await average_rating_for_service(obj_id)
        await message.answer(f'Услуга {obj_id} — средняя оценка: {avg:.2f} ({cnt} отзывов)')
    else:
        await message.answer('Тип должен быть master или service')