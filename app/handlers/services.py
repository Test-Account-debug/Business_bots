from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from app.repo import list_services
from app.repo import average_rating_for_service
from app.utils import format_rating

router = Router()

PAGE_SIZE = 5

async def _build_services_page(services, page: int):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = services[start:end]
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb_rows = []
    text_lines = []
    for s in page_items:
        avg, cnt = await average_rating_for_service(s['id'])
        rating_str = format_rating(avg, cnt)
        text = f"{s['name']} — {s['price']}\n"
        if rating_str:
            text += f"{rating_str}\n"
        text += s.get('description','')
        text_lines.append(text)
        kb_rows.append([InlineKeyboardButton(text=f'Записаться: {s["name"]}', callback_data=f'book:service:{s["id"]}')])

    # navigation
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text='⬅️ Назад', callback_data=f'services:page:{page-1}'))
    if end < len(services):
        nav_row.append(InlineKeyboardButton(text='➡️ Далее', callback_data=f'services:page:{page+1}'))
    if nav_row:
        kb_rows.append(nav_row)
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    text = "\n\n".join(text_lines) or 'Нет доступных услуг.'
    return text, kb

@router.message(Command('services'))
async def cmd_services(message: Message):
    services = await list_services()
    text, kb = await _build_services_page(services, 0)
    await message.answer(text, reply_markup=kb)

@router.callback_query(lambda q: q.data and q.data.startswith('services:page:'))
async def cb_services_page(query: CallbackQuery):
    try:
        page = int(query.data.split(':')[-1])
    except Exception:
        await query.answer('Неверная страница')
        return
    services = await list_services()
    text, kb = await _build_services_page(services, page)
    try:
        # edit existing message for smoother UX
        await query.message.edit_text(text, reply_markup=kb)
    except Exception:
        await query.message.answer(text, reply_markup=kb)
    await query.answer("")
