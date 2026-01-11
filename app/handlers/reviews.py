from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.repo import create_review, list_reviews, average_rating_for_master, average_rating_for_service, get_or_create_user
from app.notify import notify_admins

router = Router()

MAX_REVIEW_TEXT = 2000

@router.message(Command('leave_review'))
async def cmd_leave_review(message: Message):
    """Usage: /leave_review service_id|master_id|rating|text
    service_id or master_id can be empty (use 0) but at least one must be provided.
    rating: int 1-5
    text: optional text
    """
    args = message.get_args()
    if not args or '|' not in args:
        await message.answer('Использование: /leave_review service_id|master_id|rating|текст (master_id или service_id можно оставить 0)')
        return
    parts = [x.strip() for x in args.split('|', 3)]
    try:
        service_id = int(parts[0]) if parts[0] else None
    except Exception:
        await message.answer('Неверный service_id')
        return
    try:
        master_id = int(parts[1]) if parts[1] else None
    except Exception:
        await message.answer('Неверный master_id')
        return
    if not service_id and not master_id:
        await message.answer('Укажите service_id или master_id')
        return
    try:
        rating = int(parts[2])
        if not (1 <= rating <= 5):
            raise Exception('out of range')
    except Exception:
        await message.answer('Оценка должна быть целым числом от 1 до 5')
        return
    text = parts[3] if len(parts) > 3 else None
    if text and len(text) > MAX_REVIEW_TEXT:
        await message.answer(f'Текст отзыва слишком длинный (макс {MAX_REVIEW_TEXT} символов)')
        return
    # ensure user exists
    user = await get_or_create_user(message.from_user.id)
    rid = await create_review(user['id'], service_id, master_id, rating, text)
    await message.answer('Спасибо! Отзыв сохранён.')
    # notify admins
    await notify_admins(f"Новый отзыв: id={rid} рейтинг={rating} мастер={master_id} услуга={service_id} текст={text or ''}")

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