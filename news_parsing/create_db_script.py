import asyncio
from database import init_db

async def main():
    await init_db()
    print("✅ База данных создана! Файл news.db должен появиться в папке проекта")

if __name__ == "__main__":
    asyncio.run(main())