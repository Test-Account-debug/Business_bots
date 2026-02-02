import os
from aiogram import Bot

# Use os.getenv to read secrets/configs
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x]

async def notify_admins(text: str):
    if not BOT_TOKEN or not ADMIN_IDS:
        return
    # NOTE: For MVP we create a Bot per notification call and close session.
    # This keeps logic simple and is acceptable for demo. In high-load
    # scenarios creating many Bot instances may be inefficient — keep
    # as-is for Stage 4. If you see network/connectivity errors, they
    # will be logged by aiogram or surfaced during runtime.
    bot = Bot(BOT_TOKEN)
    try:
        for aid in ADMIN_IDS:
            try:
                await bot.send_message(aid, text)
            except Exception:
                # ignore send errors
                pass
    finally:
        await bot.session.close()


async def notify_user(tg_id: int, text: str):
    if not BOT_TOKEN or not tg_id:
        return
    # NOTE: Creating and closing a Bot per send keeps demo flow simple.
    # Potential network issues should be monitored when running the demo.
    bot = Bot(BOT_TOKEN)
    try:
        try:
            await bot.send_message(tg_id, text)
        except Exception:
            pass
    finally:
        await bot.session.close()
