from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
import os
from app.repo import create_master, create_service, list_bookings, set_master_schedule, delete_master, delete_service, update_master, update_service, get_master, get_service
from app.scheduler import add_exception, list_exceptions

router = Router()
ADMIN_IDS = [int(x) for x in os.environ.get('ADMIN_IDS','').split(',') if x]

# Simple in-memory staging for multi-step admin dialogs (per admin user)
STAGED_EDITS = {}
# Format: STAGED_EDITS[user_id] = { 'type': 'master'|'service', 'id': int, 'step': 'name'|'bio'|'contact'|..., 'data': {...} }

# Validation limits
MAX_NAME_LEN = 100
MAX_BIO_LEN = 1000
MAX_CONTACT_LEN = 200
MAX_DESC_LEN = 2000
MIN_PRICE = 0.0
MAX_PRICE = 1_000_000.0
MIN_DURATION = 1
MAX_DURATION = 24 * 60  # minutes


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command('admin'))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    await message.answer('Админ‑панель: /add_master name|bio|contact  /add_service name|price|duration_minutes|description  /list_bookings /export')

@router.message(Command('add_master'))
async def cmd_add_master(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = message.get_args()
    if not args or '|' not in args:
        await message.answer('Использование: /add_master Имя|bio|контакт')
        return
    name, bio, contact = [x.strip() for x in args.split('|', 2)]
    mid = await create_master(name, bio, contact)
    await message.answer(f'Мастер добавлен с id={mid}')

@router.message(Command('add_service'))
async def cmd_add_service(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = message.get_args()
    if not args or '|' not in args:
        await message.answer('Использование: /add_service Название|цена|длительность_мин|описание')
        return
    name, price, duration, description = [x.strip() for x in args.split('|', 3)]
    try:
        price_v = float(price)
        duration_v = int(duration)
    except Exception:
        await message.answer('Неверный формат цены или длительности')
        return
    sid = await create_service(name, description, price_v, duration_v)
    await message.answer(f'Услуга добавлена id={sid}')

@router.message(Command('set_schedule'))
async def cmd_set_schedule(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = message.get_args()
    # usage: /set_schedule master_id|weekday(0-6)|09:00|17:00|interval_minutes
    if not args or '|' not in args:
        await message.answer('Использование: /set_schedule master_id|weekday(0-6)|start|end|[interval_minutes]')
        return
    parts = [x.strip() for x in args.split('|')]
    try:
        master_id = int(parts[0])
        weekday = int(parts[1])
        start = parts[2]
        end = parts[3]
        interval = int(parts[4]) if len(parts) > 4 else None
    except Exception:
        await message.answer('Неверный формат аргументов')
        return
    await set_master_schedule(master_id, weekday, start, end, interval)
    await message.answer('Расписание сохранено')

@router.message(Command('add_exception'))
async def cmd_add_exception(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = message.get_args()
    # usage: /add_exception master_id|YYYY-MM-DD|available(0|1)|[start]|[end]|[note]
    if not args or '|' not in args:
        await message.answer('Использование: /add_exception master_id|YYYY-MM-DD|available(0|1)|[start]|[end]|[note]')
        return
    parts = [x.strip() for x in args.split('|')]
    try:
        master_id = int(parts[0])
        date_s = parts[1]
        available = int(parts[2])
        start = parts[3] if len(parts) > 3 and parts[3] else None
        end = parts[4] if len(parts) > 4 and parts[4] else None
        note = parts[5] if len(parts) > 5 else None
    except Exception:
        await message.answer('Неверный формат аргументов')
        return
    await add_exception(master_id, date_s, available, start, end, note)
    await message.answer('Исключение добавлено/обновлено')

@router.message(Command('list_exceptions'))
async def cmd_list_exceptions(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = message.get_args()
    if not args:
        await message.answer('Использование: /list_exceptions master_id')
        return
    try:
        master_id = int(args.strip())
    except Exception:
        await message.answer('Неверный master_id')
        return
    rows = await list_exceptions(master_id)
    if not rows:
        await message.answer('Исключений нет')
        return
    text = ''
    for r in rows:
        text += f"{r['date']} available={r['available']} {r['start_time'] or ''}-{r['end_time'] or ''} {r['note'] or ''}\n"
    await message.answer(text)

@router.message(Command('list_bookings'))
async def cmd_list_bookings(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = message.get_args()
    # optional args: start|end (YYYY-MM-DD)
    if args and '|' in args:
        start, end = [x.strip() for x in args.split('|',1)]
        rows = await list_bookings()
        rows = [r for r in rows if (r['date'] >= start and r['date'] <= end)]
    else:
        rows = await list_bookings()
    if not rows:
        await message.answer('Записей нет')
        return
    text = ''
    for r in rows[:200]:
        text += f"ID:{r['id']} {r['date']} {r['time']} user:{r['user_id']} service:{r['service_id']} master:{r['master_id']}\n"
    await message.answer(text)


@router.message(Command('complete_booking'))
async def cmd_complete_booking(message: Message):
    """Mark a booking as completed and send a review request to the client."""
    if not is_admin(message.from_user.id):
        await message.answer('🚫 Доступ запрещён. Только для администраторов.')
        return
    args = message.get_args()
    if not args:
        await message.answer('Использование: /complete_booking booking_id\nПример: /complete_booking 123')
        return
    try:
        bid = int(args.strip())
    except Exception:
        await message.answer('Неверный booking_id. Укажите число, например: 123')
        return
    await set_booking_status(bid, 'completed')
    b = await get_booking(bid)
    if not b:
        await message.answer('❌ Бронирование не найдено. Проверьте ID.')
        return
    # send review prompt to the user
    user = await get_user_by_id(b['user_id'])
    if not user or not user['tg_id']:
        await message.answer('❌ Не удалось найти Telegram ID клиента. Возможно, пользователь не зарегистрирован.')
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = [[InlineKeyboardButton(text=str(i), callback_data=f'review:rating:{i}:booking:{bid}') for i in range(1,6)], [InlineKeyboardButton(text='Добавить комментарий', callback_data=f'review:text:booking:{bid}')]]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await message.bot.send_message(user['tg_id'], 'Спасибо, что выбрали нас! ⭐ Как прошёл ваш визит? Оцените от 1 до 5 и поделитесь впечатлениями.', reply_markup=kb)
        await message.answer('✅ Отлично! Клиенту отправлен запрос на отзыв. 📝')
    except Exception as e:
        await message.answer('❌ Ошибка при отправке сообщения клиенту: ' + str(e))

@router.message(Command('export_bookings'))
async def cmd_export_bookings(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    from app.admin_utils import export_bookings_csv_bytes
    from aiogram.types import InputFile
    from io import BytesIO
    try:
        data = await export_bookings_csv_bytes()
        bio = BytesIO(data)
        bio.seek(0)
        # send BytesIO directly as document; some aiogram versions accept file-like objects
        await message.bot.send_document(message.chat.id, bio, filename='export.csv', caption='Экспорт записей', disable_notification=True)
        await message.answer('Экспорт отправлен')
    except Exception as e:
        await message.answer('Ошибка экспорта: ' + str(e))

@router.message(Command('delete_master'))
async def cmd_delete_master(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = message.get_args()
    if not args:
        await message.answer('Использование: /delete_master master_id')
        return
    try:
        mid = int(args.strip())
    except Exception:
        await message.answer('Неверный master_id')
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Подтвердить удаление', callback_data=f'confirm_delete_master:{mid}'),
        InlineKeyboardButton(text='Отменить', callback_data=f'cancel_delete_master:{mid}')
    ]])
    await message.answer(f'Вы уверены, что хотите удалить мастера {mid}?', reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith('confirm_delete_master:'))
async def cb_confirm_delete_master(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    try:
        mid = int(callback.data.split(':',1)[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    await delete_master(mid)
    # edit message or send new
    try:
        await callback.message.edit_text(f'Мастер {mid} удалён')
    except Exception:
        await callback.message.answer(f'Мастер {mid} удалён')
    await callback.answer('Удалено')



@router.callback_query(lambda c: c.data and c.data.startswith('cancel_delete_master:'))
async def cb_cancel_delete_master(callback: CallbackQuery):
    try:
        mid = int(callback.data.split(':',1)[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    try:
        await callback.message.edit_text(f'Удаление мастера {mid} отменено')
    except Exception:
        await callback.message.answer(f'Удаление мастера {mid} отменено')
    await callback.answer('Отменено')

@router.message(Command('edit_master'))
async def cmd_edit_master(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    # usage: /edit_master id|Name|bio|contact  OR /edit_master id  (start interactive)
    args = message.get_args()
    if not args:
        await message.answer('Использование: /edit_master id|Name|bio|contact  OR /edit_master id (для интерактивного редактирования)')
        return
    if '|' in args:
        try:
            parts = [x.strip() for x in args.split('|',3)]
            mid = int(parts[0])
            name = parts[1] or None
            bio = parts[2] or None
            contact = parts[3] or None
        except Exception:
            await message.answer('Неверный формат аргументов')
            return
        await update_master(mid, name=name, bio=bio, contact=contact)
        await message.answer('Мастер обновлён')
        return
    # start interactive flow
    try:
        mid = int(args.strip())
    except Exception:
        await message.answer('Неверный id')
        return
    # fetch current data
    m = await get_master(mid)
    if not m:
        await message.answer('Мастер не найден')
        return
    STAGED_EDITS[message.from_user.id] = {'type':'master', 'id': mid, 'step':'name', 'data': {'name': m['name'], 'bio': m['bio'], 'contact': m['contact']}}
    await message.answer(f"Введите новое имя мастера — кратко и понятно (пример: Иван Иванов). Оставьте пустым, чтобы сохранить текущее: {m['name']}")


@router.message(Command('edit_service'))
async def cmd_edit_service(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    # usage: /edit_service id|Name|price|duration|description  OR /edit_service id (interactive)
    args = message.get_args()
    if not args:
        await message.answer('Использование: /edit_service id|Name|price|duration|description  OR /edit_service id (для интерактивного редактирования)')
        return
    if '|' in args:
        try:
            parts = [x.strip() for x in args.split('|',4)]
            sid = int(parts[0])
            name = parts[1] or None
            price = float(parts[2]) if parts[2] else None
            duration = int(parts[3]) if parts[3] else None
            desc = parts[4] or None
        except Exception:
            await message.answer('Неверный формат аргументов')
            return
        await update_service(sid, name=name, description=desc, price=price, duration_minutes=duration)
        await message.answer('Услуга обновлена')
        return
    try:
        sid = int(args.strip())
    except Exception:
        await message.answer('Неверный id')
        return
    s = await get_service(sid)
    if not s:
        await message.answer('Услуга не найдена')
        return
    STAGED_EDITS[message.from_user.id] = {'type':'service', 'id': sid, 'step':'name', 'data': {'name': s['name'], 'description': s['description'], 'price': s['price'], 'duration_minutes': s['duration_minutes']}}
    await message.answer(f"Введите новое название услуги (пример: Маникюр, оставить пустым чтобы оставить текущее: {s['name']})")

@router.message(Command('delete_service'))
async def cmd_delete_service(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = message.get_args()
    if not args:
        await message.answer('Использование: /delete_service service_id')
        return
    try:
        sid = int(args.strip())
    except Exception:
        await message.answer('Неверный service_id')
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Подтвердить удаление', callback_data=f'confirm_delete_service:{sid}'),
        InlineKeyboardButton(text='Отменить', callback_data=f'cancel_delete_service:{sid}')
    ]])
    await message.answer(f'Вы уверены, что хотите удалить услугу {sid}?', reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith('confirm_delete_service:'))
async def cb_confirm_delete_service(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    try:
        sid = int(callback.data.split(':',1)[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    await delete_service(sid)
    try:
        await callback.message.edit_text(f'Услуга {sid} удалена')
    except Exception:
        await callback.message.answer(f'Услуга {sid} удалена')
    await callback.answer('Удалено')


@router.callback_query(lambda c: c.data and c.data.startswith('cancel_delete_service:'))
async def cb_cancel_delete_service(callback: CallbackQuery):
    try:
        sid = int(callback.data.split(':',1)[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    try:
        await callback.message.edit_text(f'Удаление услуги {sid} отменено')
    except Exception:
        await callback.message.answer(f'Удаление услуги {sid} отменено')
    await callback.answer('Отменено')

@router.message(lambda m: m.from_user and m.from_user.id in STAGED_EDITS)
async def handle_staged_edit(message: Message):
    """Handle messages while an admin has an active staged edit."""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer('Доступ запрещён')
        return
    staged = STAGED_EDITS.get(user_id)
    if not staged:
        # shouldn't happen but guard
        return
    t = staged['type']
    step = staged['step']

    text = (message.text or '').strip()

    if t == 'master':
        if step == 'name':
            if text:
                if len(text) > MAX_NAME_LEN:
                    await message.answer(f'Имя слишком длинное (макс {MAX_NAME_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['name'] = text
            staged['step'] = 'bio'
            await message.answer(f"Введите короткое описание (bio). Пример: 'Опытный мастер по стрижкам' (макс {MAX_BIO_LEN} символов). Оставьте пустым, чтобы сохранить текущее: {staged['data'].get('bio')}")
            return
        if step == 'bio':
            if text:
                if len(text) > MAX_BIO_LEN:
                    await message.answer(f'Bio слишком длинное (макс {MAX_BIO_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['bio'] = text
            staged['step'] = 'contact'
            await message.answer(f"Введите контакт (например: +7 900 000-00-00 или @username). Оставьте пустым, чтобы сохранить текущее: {staged['data'].get('contact')}")
            return
        if step == 'contact':
            if text:
                if len(text) > MAX_CONTACT_LEN:
                    await message.answer(f'Контакт слишком длинный (макс {MAX_CONTACT_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['contact'] = text
            # show confirmation
            d = staged['data']
            summary = f"Подтвердите изменения для мастера {staged['id']}:\nИмя: {d.get('name')}\nBio: {d.get('bio')}\nКонтакт: {d.get('contact')}"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='Применить', callback_data=f'confirm_apply_edit:master:{staged["id"]}:{user_id}'),
                InlineKeyboardButton(text='Отменить', callback_data=f'cancel_apply_edit:{user_id}')
            ]])
            staged['step'] = 'confirm'
            await message.answer(summary, reply_markup=kb)
            return
    elif t == 'service':
        if step == 'name':
            if text:
                if len(text) > MAX_NAME_LEN:
                    await message.answer(f'Имя слишком длинное (макс {MAX_NAME_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['name'] = text
            staged['step'] = 'price'
            await message.answer(f"Введите цену (пример: 12.5). Допустимый диапазон: {MIN_PRICE} — {MAX_PRICE}. Оставьте пустым, чтобы сохранить текущее: {staged['data'].get('price')}")
            return
        if step == 'price':
            if text:
                try:
                    v = float(text)
                except Exception:
                    await message.answer('Неверный формат цены. Введите число, например: 12.5')
                    return
                if not (MIN_PRICE <= v <= MAX_PRICE):
                    await message.answer(f'Цена должна быть между {MIN_PRICE} и {MAX_PRICE}. Введите корректное значение, например 12.5')
                    return
                staged['data']['price'] = v
            staged['step'] = 'duration'
            await message.answer(f"Введите длительность в минутах (пример: 30). Допустимый диапазон: {MIN_DURATION} — {MAX_DURATION} минут. Оставьте пустым, чтобы сохранить текущее: {staged['data'].get('duration_minutes')}")
            return
        if step == 'duration':
            if text:
                try:
                    v = int(text)
                except Exception:
                    await message.answer('Неверный формат длительности. Введите целое число, например: 45')
                    return
                if not (MIN_DURATION <= v <= MAX_DURATION):
                    await message.answer(f'Длительность должна быть между {MIN_DURATION} и {MAX_DURATION} минут. Введите корректное значение, например: 30')
                    return
                staged['data']['duration_minutes'] = v
            staged['step'] = 'description'
            await message.answer(f"Введите описание (оставьте пустым чтобы оставить текущее: {staged['data'].get('description')})")
            return
        if step == 'description':
            if text:
                if len(text) > MAX_DESC_LEN:
                    await message.answer(f'Описание слишком длинное (макс {MAX_DESC_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['description'] = text
            d = staged['data']
            summary = f"Подтвердите изменения для услуги {staged['id']}:\nИмя: {d.get('name')}\nЦена: {d.get('price')}\nДлительность: {d.get('duration_minutes')}\nОписание: {d.get('description')}"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='Применить', callback_data=f'confirm_apply_edit:service:{staged["id"]}:{user_id}'),
                InlineKeyboardButton(text='Отменить', callback_data=f'cancel_apply_edit:{user_id}')
            ]])
            staged['step'] = 'confirm'
            await message.answer(summary, reply_markup=kb)
            return


@router.callback_query(lambda c: c.data and c.data.startswith('confirm_apply_edit:'))
async def cb_confirm_apply_edit(callback: CallbackQuery):
    # format: confirm_apply_edit:<type>:<id>:<author_user_id>
    parts = callback.data.split(':')
    if len(parts) != 4:
        await callback.answer('Неверные данные', show_alert=True)
        return
    _, typ, obj_id_s, author_id_s = parts
    try:
        obj_id = int(obj_id_s)
        author_id = int(author_id_s)
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    if callback.from_user.id != author_id:
        await callback.answer('Только автор может подтвердить изменения', show_alert=True)
        return
    if not is_admin(callback.from_user.id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    staged = STAGED_EDITS.pop(author_id, None)
    if not staged:
        await callback.answer('Нечего применять', show_alert=True)
        return
    try:
        if typ == 'master':
            d = staged['data']
            await update_master(obj_id, name=d.get('name'), bio=d.get('bio'), contact=d.get('contact'))
            await callback.message.edit_text(f'Изменения для мастера {obj_id} применены')
        elif typ == 'service':
            d = staged['data']
            await update_service(obj_id, name=d.get('name'), description=d.get('description'), price=d.get('price'), duration_minutes=d.get('duration_minutes'))
            await callback.message.edit_text(f'Изменения для услуги {obj_id} применены')
        else:
            await callback.answer('Неверный тип', show_alert=True)
            return
    except Exception as e:
        await callback.message.answer('Ошибка при применении: ' + str(e))
    await callback.answer('Готово')


@router.callback_query(lambda c: c.data and c.data.startswith('cancel_apply_edit:'))
async def cb_cancel_apply_edit(callback: CallbackQuery):
    # format: cancel_apply_edit:<author_user_id>
    parts = callback.data.split(':')
    if len(parts) != 2:
        await callback.answer('Неверные данные', show_alert=True)
        return
    try:
        author_id = int(parts[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    if callback.from_user.id != author_id:
        await callback.answer('Только автор может отменить', show_alert=True)
        return
    STAGED_EDITS.pop(author_id, None)
    try:
        await callback.message.edit_text('Редактирование отменено')
    except Exception:
        await callback.message.answer('Редактирование отменено')
    await callback.answer('Отменено')
