# migration_approval_queue.py
import asyncio

import aiosqlite

from database import init_db

async def add_approval_queue_table():
    async with aiosqlite.connect("news.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS approval_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            title TEXT,
            news_text TEXT,
            image_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_processing BOOLEAN DEFAULT FALSE
        )
        """)
        await db.commit()
        print("✅ Таблица approval_queue создана")

async def main():
    await init_db()
    await add_approval_queue_table()
    print("✅ База данных обновлена!")

if __name__ == "__main__":
    asyncio.run(main())