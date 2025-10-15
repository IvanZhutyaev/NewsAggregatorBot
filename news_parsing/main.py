import asyncio
from bot import dp, bot
from parser import scheduler
import logging
import sys

async def main():
    print("🤖 Бот запускается...")
    try:
        parser_task = asyncio.create_task(scheduler())
        await dp.start_polling(
            bot,
            handle_signals=False,
            allowed_updates=dp.resolve_used_update_types()
        )
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")
    finally:
        if 'parser_task' in locals():
            parser_task.cancel()
            try:
                await parser_task
            except asyncio.CancelledError:
                print("✅ Фоновая задача парсера остановлена")
            except Exception as e:
                print(f"⚠️ Ошибка при остановке парсера: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
