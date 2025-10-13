import aiosqlite

DB_NAME = "news.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS news_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE
        )
        """)
        await db.commit()

async def add_site(url):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO sites(url) VALUES(?)", (url,))
        await db.commit()

async def remove_site(url):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM sites WHERE url=?", (url,))
        await db.commit()

async def get_sites():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT url FROM sites")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

async def is_news_sent(link):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id FROM news_sent WHERE link=?", (link,))
        return await cursor.fetchone() is not None

async def mark_news_sent(link):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO news_sent(link) VALUES(?)", (link,))
        await db.commit()
