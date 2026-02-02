from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from app.repo import list_services, average_rating_for_service
from app.utils import format_rating

router = Router()

@router.message(Command('start'))
async def cmd_start(message: Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🏢 О салоне'), KeyboardButton(text='💬 Контакты')],
            [KeyboardButton(text='💇 Услуги'), KeyboardButton(text='📅 Запись')],
            [KeyboardButton(text='⭐ Отзывы'), KeyboardButton(text='🤖 Помощник')]
        ],
        resize_keyboard=True
    )
    await message.answer('👋 Привет! Я ваш помощник по записи и вопросам. Выберите действие:', reply_markup=kb)

@router.message(lambda message: message.text and '💇' in message.text)
async def show_services(message: Message):
    services = await list_services()
    if not services:
        await message.answer('😔 Пока нет доступных услуг. Администратор скоро добавит. Попробуйте позже!')
        return
    rows = []
    for s in services:
        avg, cnt = await average_rating_for_service(s['id'])
        rating_str = format_rating(avg, cnt)
        btn_text = f"{s['name']} — {s['price']}"
        rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"book:service:{s['id']}")])
        # send individual message per service with rating (keeps existing behavior similar to /services)
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer('💇 Выберите услугу для записи:', reply_markup=kb)
