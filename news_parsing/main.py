import asyncio
from bot import dp, bot
from parser import scheduler


async def main():
    print("🤖 Бот запускается...")

    # Запускаем фоновую задачу парсера
    asyncio.create_task(scheduler())

    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print("⚠️ Ошибка polling:", e)
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())