import asyncio
from dotenv import load_dotenv
import os

# Load local env file first for demo overrides, then default .env
load_dotenv('.env.local')
load_dotenv()

from app.bot import start_bot

if __name__ == '__main__':
    asyncio.run(start_bot())


