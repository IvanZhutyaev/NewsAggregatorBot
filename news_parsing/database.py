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
        # Новая таблица для опубликованных новостей
        await db.execute("""
        CREATE TABLE IF NOT EXISTS published_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            published_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    """Проверяет, отправлялась ли новость на модерацию"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id FROM news_sent WHERE link=?", (link,))
        return await cursor.fetchone() is not None

async def mark_news_sent(link):
    """Отмечает новость как отправленную на модерацию"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO news_sent(link) VALUES(?)", (link,))
        await db.commit()

async def is_news_published(link):
    """Проверяет, была ли новость уже опубликована"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id FROM published_news WHERE link=?", (link,))
        return await cursor.fetchone() is not None

async def mark_news_published(link):
    """Отмечает новость как опубликованную"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO published_news(link) VALUES(?)", (link,))
        await db.commit()

async def cleanup_old_pending_news(days=7):
    """Очищает старые новости из pending_news (опционально)"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Удаляем новости старше X дней из news_sent, но не из published_news
        await db.execute("""
            DELETE FROM news_sent 
            WHERE link IN (
                SELECT ns.link FROM news_sent ns
                LEFT JOIN published_news pn ON ns.link = pn.link
                WHERE pn.link IS NULL 
                AND date(ns.id) < date('now', ?)
            )
        """, (f"-{days} days",))
        await db.commit()