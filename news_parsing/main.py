import asyncio
import time
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from bot import dp, on_startup
from parser import periodic_rss_check, process_queue_automatically


async def main():
    # Инициализация бота
    bot = Bot(token=BOT_TOKEN)

    # Запускаем инициализацию
    await on_startup()

    # Запускаем бота
    print("🤖 Бот запущен!")

    # Создаем фоновые задачи
    async def background_tasks():
        while True:
            try:
                # Проверяем RSS каждые 10 минут
                await periodic_rss_check()

                # Обрабатываем очередь каждые 5 минут
                await process_queue_automatically()

            except Exception as e:
                print(f"❌ Ошибка в фоновых задачах: {e}")

            # Ждем 5 минут до следующей проверки
            await asyncio.sleep(300)  # 5 минут

    # Запускаем фоновые задачи
    asyncio.create_task(background_tasks())

    # Запускаем поллинг бота
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Ошибка поллинга: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
