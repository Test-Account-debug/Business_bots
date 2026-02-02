from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from app.repo import list_services
from app.repo import average_rating_for_service
from app.utils import format_rating

router = Router()

@router.message(Command('services'))
async def cmd_services(message: Message):
    services = await list_services()
    if not services:
        await message.answer('Нет доступных услуг.')
        return
    for s in services:
        avg, cnt = await average_rating_for_service(s['id'])
        rating_str = format_rating(avg, cnt)
        rows = [[InlineKeyboardButton(text='Записаться', callback_data=f'book:service:{s["id"]}')]]
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        text = f"{s['name']} — {s['price']}\n"
        if rating_str:
            text += f"{rating_str}\n"
        text += s.get('description','')
        await message.answer(text, reply_markup=kb)
