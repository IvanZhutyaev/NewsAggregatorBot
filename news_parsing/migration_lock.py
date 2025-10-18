import asyncio

import aiosqlite

from database import init_db

async def add_lock_table():
    async with aiosqlite.connect("news.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS moderation_lock (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            is_locked BOOLEAN DEFAULT FALSE,
            locked_until DATETIME DEFAULT NULL
        )
        """)
        await db.execute("INSERT OR IGNORE INTO moderation_lock (id, is_locked) VALUES (1, FALSE)")
        await db.commit()
    print("✅ Таблица блокировки модерации добавлена!")

if __name__ == "__main__":
    asyncio.run(add_lock_table())