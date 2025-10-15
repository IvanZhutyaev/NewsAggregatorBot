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
        await db.execute("""
        CREATE TABLE IF NOT EXISTS published_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            published_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.execute("""
                CREATE TABLE IF NOT EXISTS processing_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link TEXT UNIQUE,
                    title TEXT,
                    news_text TEXT,
                    image_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_processing BOOLEAN DEFAULT FALSE,
                    processed_by INTEGER DEFAULT NULL
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


async def add_to_queue(link: str, title: str, news_text: str, image_path: str):
    """Добавляет новость в очередь обработки"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR IGNORE INTO processing_queue (link, title, news_text, image_path)
            VALUES (?, ?, ?, ?)
        """, (link, title, news_text, image_path))
        await db.commit()


async def get_next_from_queue():
    """Получает следующую новость из очереди для обработки"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Ищем первую необрабатываемую новость
        cursor = await db.execute("""
            SELECT id, link, title, news_text, image_path 
            FROM processing_queue 
            WHERE is_processing = FALSE 
            ORDER BY created_at ASC 
            LIMIT 1
        """)
        news = await cursor.fetchone()

        if news:
            # Помечаем как обрабатываемую
            await db.execute("""
                UPDATE processing_queue 
                SET is_processing = TRUE 
                WHERE id = ?
            """, (news[0],))
            await db.commit()

        return news


async def mark_queue_processed(link: str):
    """Помечает новость в очереди как обработанную (удаляет из очереди)"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM processing_queue WHERE link = ?", (link,))
        await db.commit()


async def get_queue_size():
    """Возвращает размер очереди"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM processing_queue")
        result = await cursor.fetchone()
        return result[0] if result else 0


async def clear_stuck_processing():
    """Очищает зависшие обработки (старше 10 минут)"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE processing_queue 
            SET is_processing = FALSE 
            WHERE is_processing = TRUE 
            AND datetime(created_at) < datetime('now', '-10 minutes')
        """)
        await db.commit()
async def add_to_approval_queue(link: str, title: str, news_text: str, image_path: str):
    """Добавляет новость в очередь одобрения"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR IGNORE INTO approval_queue (link, title, news_text, image_path)
            VALUES (?, ?, ?, ?)
        """, (link, title, news_text, image_path))
        await db.commit()

async def get_next_from_approval_queue():
    """Получает следующую новость из очереди одобрения"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id, link, title, news_text, image_path 
            FROM approval_queue 
            WHERE is_processing = FALSE 
            ORDER BY created_at ASC 
            LIMIT 1
        """)
        news = await cursor.fetchone()

        if news:
            await db.execute("""
                UPDATE approval_queue 
                SET is_processing = TRUE 
                WHERE id = ?
            """, (news[0],))
            await db.commit()

        return news

async def mark_approval_processed(link: str):
    """Помечает новость в очереди одобрения как обработанную"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM approval_queue WHERE link = ?", (link,))
        await db.commit()