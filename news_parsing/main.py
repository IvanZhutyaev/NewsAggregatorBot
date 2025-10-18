import asyncio
from bot import dp, bot
from parser import scheduler
import logging
import sys


async def main():
    print("🤖 Бот запускается...")
    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            print(f"🔄 Попытка запуска {attempt + 1}/{max_retries}...")

            # Запускаем парсер ВНЕ зависимости от успешности бота
            parser_task = asyncio.create_task(scheduler())

            # Запускаем бота
            await dp.start_polling(
                bot,
                handle_signals=False,
                allowed_updates=dp.resolve_used_update_types()
            )
            break

        except Exception as e:
            print(f"❌ Ошибка бота (попытка {attempt + 1}): {e}")

            if attempt < max_retries - 1:
                print(f"⏳ Повторная попытка через {retry_delay} секунд...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Экспоненциальная задержка
            else:
                print("❌ Не удалось запустить бота после всех попыток")
                # Но парсер продолжает работать!
                try:
                    await parser_task
                except asyncio.CancelledError:
                    print("✅ Фоновая задача парсера остановлена")
                return

    # Если бот запустился, ждем завершения парсера
    try:
        await parser_task
    except asyncio.CancelledError:
        print("✅ Фоновая задача парсера остановлена")
    except Exception as e:
        print(f"⚠️ Ошибка в парсере: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()