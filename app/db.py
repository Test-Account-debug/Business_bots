import aiosqlite
import os
import glob
from contextlib import asynccontextmanager

def _db_path():
    # Read DATABASE_URL via getenv so .env.local can override in demo setups
    return os.getenv('DATABASE_URL', 'sqlite:///./bot.db').replace('sqlite:///', '')

async def init_db():
    files = sorted(glob.glob('migrations/*.sql'))
    async with aiosqlite.connect(_db_path()) as db:

        if not files:
            # fallback schema for tests / fresh CI
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE,
                name TEXT,
                phone TEXT
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_id INTEGER,
                master_id INTEGER,
                date TEXT,
                time TEXT,
                name TEXT,
                phone TEXT,
                status TEXT DEFAULT 'active'
            );
            """)
        else:
            for p in files:
                with open(p, 'r', encoding='utf-8') as f:
                    sql = f.read()
                try:
                    await db.executescript(sql)
                except Exception as e:
                    msg = str(e).lower()
                    if 'duplicate column' in msg or 'already exists' in msg:
                        continue
                    raise

        await db.commit()



@asynccontextmanager
async def get_db():
    conn = await aiosqlite.connect(_db_path())
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()
