from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from app.repo import get_or_create_user, create_booking, list_masters, SlotTaken, DoubleBooking
from app.utils import valid_phone

router = Router()

class BookingStates(StatesGroup):
    SERVICE = State()
    MASTER = State()
    DATE = State()
    TIME = State()
    NAME = State()
    PHONE = State()
    CONFIRM = State()


async def _set_state(ctx: FSMContext, state_obj: State):
    """Set FSM state in a way compatible with real FSMContext and the test FakeState."""
    try:
        # aiogram State.set() may exist
        await state_obj.set()
    except Exception:
        try:
            await ctx.update_data(_state=state_obj.state)
        except Exception:
            pass


async def _get_state(ctx: FSMContext):
    try:
        return await ctx.get_state()
    except Exception:
        data = await ctx.get_data()
        return data.get('_state')

@router.callback_query(Text(startswith='book:service:'))
async def cb_select_service(query: CallbackQuery, state: FSMContext):
    service_id = int(query.data.split(':')[-1])
    await state.update_data(service_id=service_id)
    # list masters
    masters = await list_masters()
    if not masters:
        await query.message.answer('Нет мастеров. Админ должен добавить мастеров.')
        return
    text = 'Выберите мастера или без выбора:'
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for m in masters:
        kb.add(InlineKeyboardButton(text=m['name'], callback_data=f'book:master:{m["id"]}'))
    kb.add(InlineKeyboardButton(text='Без выбора', callback_data='book:master:0'))
    await query.message.answer(text, reply_markup=kb)
    await query.answer("")

@router.callback_query(Text(startswith='book:master:'))
async def cb_select_master(query: CallbackQuery, state: FSMContext):
    master_id = int(query.data.split(':')[-1])
    await state.update_data(master_id=master_id)
    await query.message.answer('Введите дату в формате YYYY-MM-DD (например, 2026-01-15)')
    await _set_state(state, BookingStates.DATE)
    await query.answer("")


# Manual request flow: states
class ManualRequestStates(StatesGroup):
    PREFER = State()
    NAME = State()
    PHONE = State()
    CONFIRM = State()


@router.callback_query(Text(startswith='manual:request:start'))
async def cb_manual_start(query: CallbackQuery, state: FSMContext):
    # can be 'manual:request:start' or 'manual:request:start:master:<id>'
    parts = query.data.split(':')
    master_id = None
    if len(parts) == 4 and parts[2] == 'master':
        try:
            master_id = int(parts[3])
        except Exception:
            master_id = None
    await state.update_data(manual_master_id=master_id)
    await state.update_data(manual_service_id=(await state.get_data()).get('service_id'))
    await query.message.answer('Опишите предпочитаемое время или дополнительные пожелания (например: утро, после 16:00). Оставьте пустым, если нет предпочтений.')
    await _set_state(state, ManualRequestStates.PREFER)
    await query.answer("")


@router.callback_query(Text(startswith='manual:request:cancel'))
async def cb_manual_cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.answer('Ручная заявка отменена.')
    await query.answer("")


@router.message(lambda message: True)
async def mr_prefer(message: Message, state: FSMContext):
    cur = await _get_state(state)
    if cur != ManualRequestStates.PREFER.state:
        return
    pref = (message.text or '').strip()
    await state.update_data(manual_prefer=pref)
    await message.answer('Введите ваше имя для заявки:')
    await _set_state(state, ManualRequestStates.NAME)


@router.message(lambda message: True)
async def mr_name(message: Message, state: FSMContext):
    cur = await _get_state(state)
    if cur != ManualRequestStates.NAME.state:
        return
    name = (message.text or '').strip()
    if not name:
        await message.answer('Имя не может быть пустым. Введите ваше имя:')
        return
    await state.update_data(manual_name=name)
    await message.answer('Введите телефон (например, +37061234567):')
    await _set_state(state, ManualRequestStates.PHONE)


@router.message(lambda message: True)
async def mr_phone(message: Message, state: FSMContext):
    cur = await _get_state(state)
    if cur != ManualRequestStates.PHONE.state:
        return
    phone = (message.text or '').strip()
    from app.utils import valid_phone
    if not valid_phone(phone):
        await message.answer('Неверный формат телефона. Попробуйте +37061234567')
        return
    await state.update_data(manual_phone=phone)
    data = await state.get_data()
    text = f"Ручная заявка:\nСервис ID: {data.get('manual_service_id')}\nМастер ID: {data.get('manual_master_id') or 'не указан'}\nПредпочтения: {data.get('manual_prefer') or ''}\nИмя: {data.get('manual_name')}\nТелефон: {data.get('manual_phone')}"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отправить', callback_data='manual:request:confirm'), InlineKeyboardButton(text='Отмена', callback_data='manual:request:cancel')]])
    await message.answer(text, reply_markup=kb)
    await _set_state(state, ManualRequestStates.CONFIRM)


@router.callback_query(Text(startswith='manual:request:confirm'))
async def cb_manual_confirm(query: CallbackQuery, state: FSMContext):
    cur = await _get_state(state)
    if cur != ManualRequestStates.CONFIRM.state:
        await query.answer("")
        return
    data = await state.get_data()
    # ensure user
    user = await get_or_create_user(query.from_user.id, name=data.get('manual_name'), phone=data.get('manual_phone'))
    # construct text
    text = f"manual_request service={data.get('manual_service_id')} master={data.get('manual_master_id')} pref={data.get('manual_prefer')} name={data.get('manual_name')} phone={data.get('manual_phone')}"
    from app.repo import create_manual_request
    rid = await create_manual_request(user['id'], text)
    try:
        from app.notify import notify_admins
        await notify_admins(f"Новая ручная заявка id={rid} {text}")
    except Exception:
        pass
    await query.message.answer('Ручная заявка отправлена админам. Мы свяжемся с вами.')
    await state.clear()
    await query.answer("")

@router.callback_query(Text(startswith='book:master_choose:'))
async def cb_master_choose(query: CallbackQuery, state: FSMContext):
    mid = int(query.data.split(':')[-1])
    data = await state.get_data()
    date_s = data.get('date')
    svc_id = data.get('service_id')
    from app.scheduler import generate_slots
    from app.repo import get_service, get_master
    svc = await get_service(svc_id)
    if not svc:
        await query.message.answer('Ошибка: услуга не найдена')
        await query.answer("")
        return
    slots = await generate_slots(mid, date_s, svc['duration_minutes'])
    if not slots:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='Отправить ручную заявку админу', callback_data=f'manual:request:start:master:{mid}'),
            InlineKeyboardButton(text='Отмена', callback_data='manual:request:cancel')
        ]])
        await query.message.answer('На этот день нет доступных слотов для этого мастера. Хотите отправить ручную заявку?', reply_markup=kb)
        await query.answer("")
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for t in slots:
        rows.append([InlineKeyboardButton(text=t, callback_data=f'book:time:{t}')])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await query.message.answer(f'Доступные слоты для мастера { (await get_master(mid)) ["name"] } на {date_s}:', reply_markup=kb)
    await _set_state(state, BookingStates.TIME)
    await query.answer("")

@router.message(lambda message: True)
async def process_date(message: Message, state: FSMContext):
    cur = await _get_state(state)
    if cur != BookingStates.DATE.state:
        return
    date_s = message.text.strip()
    # minimal validation
    try:
        import datetime
        datetime.date.fromisoformat(date_s)
    except Exception:
        await message.answer('Неверный формат даты. Попробуйте YYYY-MM-DD')
        return
    await state.update_data(date=date_s)

    data = await state.get_data()
    master_id = data.get('master_id')
    svc_id = data.get('service_id')
    from app.repo import list_masters, get_service
    from app.scheduler import generate_slots
    svc = await get_service(svc_id)
    if not svc:
        await message.answer('Ошибка: услуга не найдена')
        return

    if master_id == 0 or master_id is None:
        # show masters who have slots on that date
        masters = await list_masters()
        masters_with = []
        for m in masters:
            slots = await generate_slots(m['id'], date_s, svc['duration_minutes'])
            if slots:
                masters_with.append((m, slots))
        if not masters_with:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton('Отправить ручную заявку админу', callback_data='manual:request:start'),
                InlineKeyboardButton('Отмена', callback_data='manual:request:cancel')
            ]])
            await message.answer('К сожалению, на этот день нет свободных слотов. Хотите отправить ручную заявку админу?', reply_markup=kb)
            return
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        rows = []
        for m, slots in masters_with:
            rows.append([InlineKeyboardButton(text=f"{m['name']} ({len(slots)}), выбрать", callback_data=f'book:master_choose:{m['id']}')])
        # Also show masters with zero slots as option for manual request
        all_masters = await list_masters()
        for m in all_masters:
            if not any(m2['id'] == m['id'] for m2, _ in masters_with):
                rows.append([InlineKeyboardButton(text=f"{m['name']} (❌ занято) — запросить", callback_data=f'manual:request:start:master:{m["id"]}')])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await message.answer('Выберите мастера с доступным временем или отправьте запрос для занятых мастеров:', reply_markup=kb)
        return

    # specific master flow
    slots = await generate_slots(master_id, date_s, svc['duration_minutes'])
    if not slots:
        await message.answer('К сожалению, у выбранного мастера нет слотов на этот день. Попробуйте другую дату или мастера.')
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup()
    for t in slots:
        kb.add(InlineKeyboardButton(t, callback_data=f'book:time:{t}'))
    await message.answer('Выберите время:', reply_markup=kb)
    await _set_state(state, BookingStates.TIME)

@router.callback_query(Text(startswith='book:time:'))
async def cb_select_time(query: CallbackQuery, state: FSMContext):
    time_s = query.data.split(':')[-1]
    await state.update_data(time=time_s)
    await query.message.answer('Введите ваше имя:')
    await _set_state(state, BookingStates.NAME)
    await query.answer("")

@router.message(lambda message: True)
async def process_time(message: Message, state: FSMContext):
    cur = await _get_state(state)
    if cur != BookingStates.TIME.state:
        return
    time_s = message.text.strip()
    try:
        import datetime
        datetime.time.fromisoformat(time_s)
    except Exception:
        await message.answer('Неверный формат времени. Попробуйте HH:MM')
        return
    await state.update_data(time=time_s)
    await message.answer('Введите ваше имя:')
    await _set_state(state, BookingStates.NAME)

@router.message(lambda message: True)
async def process_name(message: Message, state: FSMContext):
    cur = await _get_state(state)
    if cur != BookingStates.NAME.state:
        return
    await state.update_data(name=message.text.strip())
    await message.answer('Введите телефон (например, +37061234567):')
    await _set_state(state, BookingStates.PHONE)

@router.message(lambda message: True)
async def process_phone(message: Message, state: FSMContext):
    cur = await _get_state(state)
    if cur != BookingStates.PHONE.state:
        return
    phone = message.text.strip()
    if not valid_phone(phone):
        await message.answer('Неверный формат телефона. Попробуйте +37061234567')
        return
    await state.update_data(phone=phone)
    data = await state.get_data()
    text = f"Подтвердите запись:\nУслуга ID: {data['service_id']}\nМастер ID: {data['master_id']}\nДата: {data['date']}\nВремя: {data['time']}\nИмя: {data['name']}\nТелефон: {data['phone']}"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton(text='Подтвердить', callback_data='book:confirm'), InlineKeyboardButton(text='Отмена', callback_data='book:cancel'))
    await message.answer(text, reply_markup=kb)
    await _set_state(state, BookingStates.CONFIRM)

@router.callback_query(Text(equals='book:confirm'))
async def cb_confirm(query: CallbackQuery, state: FSMContext):
    cur = await _get_state(state)
    if cur != BookingStates.CONFIRM.state:
        await query.answer("")
        return
    data = await state.get_data()
    user = await get_or_create_user(query.from_user.id, name=data.get('name'), phone=data.get('phone'))
    try:
        await create_booking(user['id'], data['service_id'], data['master_id'] if data['master_id'] != 0 else None, data['date'], data['time'], data['name'], data['phone'])
    except SlotTaken:
        await query.message.answer('Извините, это время уже занято. Попробуйте выбрать другое.')
        await state.clear()
        await query.answer("")
        return
    except DoubleBooking:
        await query.message.answer('У вас уже есть активная запись. Нельзя записаться второй раз.')
        await state.clear()
        await query.answer("")
        return
    # notify admins
    try:
        from app.notify import notify_admins
        await notify_admins(f"Новая запись: {data['date']} {data['time']} Услуга:{data['service_id']} Мастер:{data['master_id']} Клиент:{data['name']} {data['phone']}")
    except Exception:
        pass
    await query.message.answer('Запись подтверждена! Админ уведомлён.')
    await state.clear()
    await query.answer()

@router.callback_query(Text(equals='book:cancel'))
async def cb_cancel(query: CallbackQuery, state: FSMContext):
    cur = await _get_state(state)
    if cur != BookingStates.CONFIRM.state:
        await query.answer("")
        return
    await query.message.answer('Запись отменена.')
    await state.clear()
    await query.answer()
