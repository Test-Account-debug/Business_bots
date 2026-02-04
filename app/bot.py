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

    # Debug helper: log every incoming message (kept for future use but not globally registered)
    # This function is NOT registered globally to avoid intercepting button handlers
    async def _debug_message(message: Message):
        try:
            text = getattr(message, 'text', None)
            print('GLOBAL MESSAGE:', getattr(message.from_user, 'id', None), repr(text), 'codepoints:', [hex(ord(c)) for c in (text or '')], 'chat:', getattr(message.chat, 'id', None))
        except Exception:
            pass

    # Register routers in order (handlers with specific filters take precedence)
    dp.include_router(client_router)
    dp.include_router(admin_router)
    dp.include_router(booking_router)
    dp.include_router(services_router)

    print('Bot started')
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
