from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from app.repo import list_services

router = Router()

@router.message(commands=['start'])
async def cmd_start(message: Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton('🏢 О салоне'), KeyboardButton('💬 Контакты')],
            [KeyboardButton('💇 Услуги'), KeyboardButton('📅 Запись')],
            [KeyboardButton('⭐ Отзывы'), KeyboardButton('🤖 Помощник')]
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
        rows.append([InlineKeyboardButton(text=f"{s['name']} — {s['price']}", callback_data=f"book:service:{s['id']}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer('💇 Выберите услугу для записи:', reply_markup=kb)
