from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
import os
from app.handlers.client import router as client_router
from app.handlers.admin import router as admin_router
from app.handlers.booking import router as booking_router
from app.handlers.services import router as services_router
from app.db import init_db

BOT_TOKEN = os.getenv('BOT_TOKEN')

async def start_bot():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    # init db
    await init_db()

    dp.include_router(client_router)
    dp.include_router(admin_router)
    dp.include_router(booking_router)
    dp.include_router(services_router)

    print('Bot started')
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
