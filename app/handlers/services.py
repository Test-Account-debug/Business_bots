from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from app.repo import list_services

router = Router()

@router.message(commands=['services'])
async def cmd_services(message: Message):
    services = await list_services()
    if not services:
        await message.answer('Нет доступных услуг.')
        return
    for s in services:
        rows = [[InlineKeyboardButton(text='Записаться', callback_data=f'book:service:{s["id"]}')]]
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await message.answer(f"{s['name']} — {s['price']}\n{s.get('description','')}", reply_markup=kb)
