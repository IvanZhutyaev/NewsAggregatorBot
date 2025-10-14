import asyncio
import os
import random
import hashlib
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError
from aiogram.types import FSInputFile
from config import BOT_TOKEN, CHANNEL_ID, ADMINS
from database import init_db, add_site, remove_site, get_sites, is_news_sent, mark_news_sent, mark_news_published, \
    get_queue_size, clear_stuck_processing, update_news_with_deepseek, mark_no_deepseek_needed
from site_poster import post_news_to_site
from parser import paraphrase_with_deepseek

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Глобальный словарь для хранения новостей в ожидании
pending_news = {}


# Отправка оригинальной новости на первичную модерацию
async def send_original_news_to_admin(original_title: str, original_text: str, source_url: str, image_path: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            news_id = hashlib.md5(source_url.encode()).hexdigest()
            pending_news[news_id] = {
                "url": source_url,
                "image": image_path,
                "original_title": original_title,
                "original_text": original_text,
                "needs_deepseek": True
            }

            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="✅ Обработать в DeepSeek", callback_data=f"process_deepseek|{news_id}")
            keyboard.button(text="📝 Опубликовать как есть", callback_data=f"publish_as_is|{news_id}")
            keyboard.button(text="❌ Отклонить", callback_data=f"reject_early|{news_id}")

            caption = f"<b>ОРИГИНАЛЬНАЯ НОВОСТЬ</b>\n\n<b>{original_title}</b>\n\n{original_text}\n\nИсточник: {source_url}"

            # Отправляем ВСЕМ админам
            sent_to_admins = 0
            for admin_id in ADMINS:
                try:
                    if len(caption) <= 1024:
                        await bot.send_photo(
                            admin_id,
                            FSInputFile(image_path),
                            caption=caption,
                            reply_markup=keyboard.as_markup(),
                            parse_mode="HTML"
                        )
                    else:
                        # Если текст слишком длинный, разделяем
                        await bot.send_photo(admin_id, FSInputFile(image_path), reply_markup=keyboard.as_markup())
                        await bot.send_message(admin_id, caption, parse_mode="HTML")
                    print(f"✅ Оригинальная новость отправлена админу {admin_id}")
                    sent_to_admins += 1
                except TelegramForbiddenError:
                    print(f"❌ Не удалось отправить админу {admin_id} — он не написал боту.")
                except Exception as e:
                    print(f"❌ Ошибка отправки админу {admin_id}: {e}")

            if sent_to_admins > 0:
                print(f"📨 Оригинальная новость отправлена {sent_to_admins} админам")
                break  # Успешно отправлено хотя бы одному админу

        except TelegramNetworkError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⚠️ Ошибка сети, повторная попытка {attempt + 1} через {wait_time} сек...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ Не удалось отправить оригинальную новость после {max_retries} попыток: {e}")
        except Exception as e:
            print(f"❌ Критическая ошибка в send_original_news_to_admin: {e}")
            break


# Отправка обработанной новости на финальную модерацию
async def send_processed_news_to_admin(news_text: str, source_url: str, image_path: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            news_id = hashlib.md5(source_url.encode()).hexdigest()
            pending_news[news_id] = {"url": source_url, "image": image_path, "text": news_text}

            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🌐 На сайт", callback_data=f"site|{news_id}")
            keyboard.button(text="✅ В Telegram", callback_data=f"approve|{news_id}")
            keyboard.button(text="🚀 Оба", callback_data=f"both|{news_id}")
            keyboard.button(text="❌ Отклонить", callback_data=f"reject|{news_id}")

            admin_caption = f"{news_text}\n\nИсточник: {source_url}"

            # Отправляем ВСЕМ админам
            sent_to_admins = 0
            for admin_id in ADMINS:
                try:
                    if len(admin_caption) <= 1024:
                        await bot.send_photo(
                            admin_id,
                            FSInputFile(image_path),
                            caption=admin_caption,
                            reply_markup=keyboard.as_markup()
                        )
                    else:
                        await bot.send_photo(admin_id, FSInputFile(image_path), reply_markup=keyboard.as_markup())
                        await bot.send_message(admin_id, admin_caption)
                    print(f"✅ Обработанная новость отправлена админу {admin_id}")
                    sent_to_admins += 1
                except TelegramForbiddenError:
                    print(f"❌ Не удалось отправить админу {admin_id} — он не написал боту.")
                except Exception as e:
                    print(f"❌ Ошибка отправки админу {admin_id}: {e}")

            if sent_to_admins > 0:
                print(f"📨 Обработанная новость отправлена {sent_to_admins} админам")
                break  # Успешно отправлено хотя бы одному админу

        except TelegramNetworkError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⚠️ Ошибка сети, повторная попытка {attempt + 1} через {wait_time} сек...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ Не удалось отправить обработанную новость после {max_retries} попыток: {e}")
        except Exception as e:
            print(f"❌ Критическая ошибка в send_processed_news_to_admin: {e}")
            break


# Обработка нажатий кнопок для оригинальных новостей
@dp.callback_query(F.data.startswith("process_deepseek|"))
async def process_with_deepseek(callback: types.CallbackQuery):
    await callback.answer("Обрабатываем в DeepSeek...")

    _, news_id = callback.data.split("|", 1)
    data = pending_news.get(news_id)
    if not data:
        await callback.message.answer("❌ Новость не найдена.")
        return

    try:
        # Обрабатываем через DeepSeek
        processed_text = paraphrase_with_deepseek(data["original_title"], data["original_text"])

        # Обновляем в базе данных
        await update_news_with_deepseek(data["url"], processed_text)

        # Удаляем из pending_news и добавляем обработанную версию
        pending_news.pop(news_id, None)

        # Отправляем обработанную новость на финальную модерацию
        await send_processed_news_to_admin(processed_text, data["url"], data["image"])

        await callback.message.answer("✅ Новость обработана в DeepSeek и отправлена на финальную модерацию!")

    except Exception as e:
        print(f"❌ Ошибка обработки в DeepSeek: {e}")
        await callback.message.answer("❌ Ошибка при обработке в DeepSeek.")


@dp.callback_query(F.data.startswith("publish_as_is|"))
async def publish_as_is(callback: types.CallbackQuery):
    await callback.answer("Публикуем как есть...")

    _, news_id = callback.data.split("|", 1)
    data = pending_news.get(news_id)
    if not data:
        await callback.message.answer("❌ Новость не найдена.")
        return

    try:
        # Помечаем, что не нужно обрабатывать в DeepSeek
        await mark_no_deepseek_needed(data["url"])

        # Отправляем оригинальную новость на финальную модерацию
        news_text = f"{data['original_title']}\n\n{data['original_text']}"
        await send_processed_news_to_admin(news_text, data["url"], data["image"])

        # Удаляем из pending_news
        pending_news.pop(news_id, None)

        await callback.message.answer("✅ Новость отправлена на финальную модерацию (без DeepSeek)!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        await callback.message.answer("❌ Ошибка при подготовке новости.")


@dp.callback_query(F.data.startswith("reject_early|"))
async def reject_early(callback: types.CallbackQuery):
    try:
        await callback.answer("Новость отклонена на раннем этапе")
    except Exception:
        pass

    _, news_id = callback.data.split("|", 1)
    data = pending_news.get(news_id)

    if data:
        # Удаляем из очереди
        from database import mark_queue_processed
        await mark_queue_processed(data["url"])
        pending_news.pop(news_id, None)

    try:
        await callback.message.delete()
    except Exception:
        pass

    # Уведомляем ВСЕХ админов об отклонении
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, "❌ Новость отклонена на раннем этапе.")
        except Exception:
            pass


# Существующие обработчики для финальной модерации (остаются без изменений)
@dp.callback_query(F.data.startswith("approve|"))
async def approve_news(callback: types.CallbackQuery):
    await callback.answer()

    _, news_id = callback.data.split("|", 1)
    data = pending_news.get(news_id)
    if not data:
        await callback.message.answer("❌ Новость не найдена.")
        return

    news_text = data["text"]
    image_path = data["image"]

    if not os.path.exists(image_path):
        print(f"❌ Файл не найден: {image_path}")
        await callback.message.answer("❌ Изображение не найдено, новость не отправлена.")
        return

    photo = FSInputFile(image_path)
    caption = news_text

    try:
        await bot.send_photo(CHANNEL_ID, photo, caption=caption, parse_mode="HTML")
    except Exception as e:
        print("❌ Ошибка отправки в канал:", e)
        await callback.message.answer("❌ Не удалось отправить новость в канал.")
        return

    # Отмечаем как опубликованную
    await mark_news_published(data["url"])
    pending_news.pop(news_id, None)

    try:
        await callback.message.delete()
    except Exception:
        pass

    # Уведомляем ВСЕХ админов о публикации
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, "✅ Новость опубликована в Telegram.")
        except Exception:
            pass


@dp.callback_query(F.data.startswith("site|"))
async def post_to_site(callback: types.CallbackQuery):
    try:
        await callback.answer()
        _, news_id = callback.data.split("|", 1)
        data = pending_news.get(news_id)
        if not data:
            await callback.message.answer("❌ Новость не найдена.")
            return

        success = post_news_to_site(data["text"], data["image"])
        if success:
            # Отмечаем как опубликованную
            await mark_news_published(data["url"])
            pending_news.pop(news_id, None)
            await callback.message.answer("🌐 Новость опубликована на сайте!")

            # Уведомляем ВСЕХ админов о публикации
            for admin_id in ADMINS:
                try:
                    await bot.send_message(admin_id, "🌐 Новость опубликована на сайте!")
                except Exception:
                    pass
        else:
            await callback.message.answer("❌ Ошибка при публикации на сайте.")
    except Exception as e:
        print(f"❌ Ошибка в post_to_site: {e}")
        await callback.message.answer("❌ Произошла ошибка при публикации на сайте.")


@dp.callback_query(F.data.startswith("both|"))
async def post_to_both(callback: types.CallbackQuery):
    try:
        await callback.answer()
        _, news_id = callback.data.split("|", 1)
        data = pending_news.get(news_id)
        if not data:
            await callback.message.answer("❌ Новость не найдена.")
            return

        image_path = data["image"]
        text = data["text"]

        # 1️⃣ Публикуем на сайт
        success_site = post_news_to_site(text, image_path)

        # 2️⃣ Публикуем в Telegram
        try:
            photo = FSInputFile(image_path)
            await bot.send_photo(CHANNEL_ID, photo, caption=text, parse_mode="HTML")
            success_tg = True
        except Exception as e:
            print("Ошибка публикации в Telegram:", e)
            success_tg = False

        # Результат
        if success_site or success_tg:  # Если хотя бы одна публикация успешна
            # Отмечаем как опубликованную
            await mark_news_published(data["url"])
            pending_news.pop(news_id, None)

            # Уведомляем ВСЕХ админов о публикации
            result_message = ""
            if success_site and success_tg:
                result_message = "🚀 Новость опубликована в Telegram и на сайте!"
            elif success_site:
                result_message = "🌐 Новость опубликована на сайте (Telegram не удалось)!"
            else:
                result_message = "✅ Новость опубликована в Telegram (сайт не удалось)!"

            await callback.message.answer(result_message)
            for admin_id in ADMINS:
                try:
                    await bot.send_message(admin_id, result_message)
                except Exception:
                    pass
        else:
            await callback.message.answer("⚠️ Ошибка при публикации (проверь лог).")
    except Exception as e:
        print(f"❌ Ошибка в post_to_both: {e}")
        await callback.message.answer("❌ Произошла ошибка при публикации.")


@dp.callback_query(F.data.startswith("reject|"))
async def reject_news(callback: types.CallbackQuery):
    try:
        await callback.answer("Новость отклонена")
    except Exception:
        pass

    _, news_id = callback.data.split("|", 1)
    data = pending_news.get(news_id)

    if data:
        pending_news.pop(news_id, None)

    try:
        await callback.message.delete()
    except Exception:
        pass

    # Уведомляем ВСЕХ админов об отклонении
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, "❌ Новость отклонена.")
        except Exception:
            pass


# Команды для админов (остаются без изменений)
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return

    help_text = """
🤖 *Панель управления Новостным Ботом*

*📋 Основные команды:*

*/start* - показать это сообщение
*/help* - справка по командам

*🌐 Управление RSS-лентами:*
*/addsite <url>* - добавить RSS-ленту
*/listsites* - показать все RSS-ленты  
*/removesite <url>* - удалить RSS-ленту

*📊 Управление очередью:*
*/queue* - статус очереди новостей
*/postnext* - обработать следующую новость
*/skipnext* - пропустить текущую новость
*/postlatest* - принудительно проверить новости

*📨 Двухэтапная модерация:*
1. *Первичная модерация* - решаем обрабатывать ли новость в DeepSeek
2. *Финальная модерация* - публикуем обработанную новость

*⚙️ Система работает так:*
1. Новости добавляются в очередь
2. Админ видит оригинал и решает:
   - ✅ Обработать в DeepSeek (платно)
   - 📝 Опубликовать как есть (бесплатно)
   - ❌ Отклонить
3. После обработки - финальное решение о публикации

Для начала работы добавьте RSS-ленты командой /addsite
    """

    await message.answer(help_text, parse_mode="Markdown")


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return

    help_text = """
📖 *Справка по командам бота*

*Добавление RSS-лент:*
`/addsite https://example.com/rss` - добавить ленту
`/listsites` - посмотреть все ленты
`/removesite https://example.com/rss` - удалить ленту

*Управление очередью:*
`/queue` - посмотреть сколько новостей ждут обработки
`/postnext` - вручную запустить обработку следующей новости
`/skipnext` - пропустить зависшую новость
`/postlatest` - принудительно проверить все RSS-ленты

*Двухэтапная модерация:*
- Сначала видите оригинальную новость
- Решаете: обработать в DeepSeek или опубликовать как есть
- Затем финальное решение о публикации

*Примеры RSS-лент:*
• https://www.agroinvestor.ru/news/rss/
• https://www.agronews.ru/rss/news.xml
• https://www.agroxxi.ru/export/rss.xml

Для начала работы добавьте хотя бы одну RSS-ленту!
    """

    await message.answer(help_text, parse_mode="Markdown")


@dp.message(Command("addsite"))
async def cmd_add_site(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажи ссылку на RSS\nНапример: `/addsite https://example.com/rss`",
                             parse_mode="Markdown")
        return

    url = args[1].strip()

    # Простая валидация URL
    if not url.startswith(('http://', 'https://')):
        await message.answer("❌ Неверный формат ссылки. Должна начинаться с http:// или https://")
        return

    try:
        await add_site(url)
        await message.answer(f"✅ RSS-лента добавлена:\n`{url}`", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка добавления: {e}")


@dp.message(Command("listsites"))
async def cmd_list_sites(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return

    sites = await get_sites()
    if not sites:
        await message.answer("📭 RSS-ленты не добавлены\nИспользуй /addsite для добавления")
        return

    sites_text = "📋 *Добавленные RSS-ленты:*\n\n"
    for i, site in enumerate(sites, 1):
        sites_text += f"{i}. `{site}`\n"

    sites_text += f"\nВсего: {len(sites)} лент"
    await message.answer(sites_text, parse_mode="Markdown")


@dp.message(Command("removesite"))
async def cmd_remove_site(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажи ссылку на RSS для удаления\nНапример: `/removesite https://example.com/rss`",
                             parse_mode="Markdown")
        return

    url = args[1].strip()

    try:
        await remove_site(url)
        await message.answer(f"✅ RSS-лента удалена:\n`{url}`", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка удаления: {e}")


@dp.message(Command("queue"))
async def cmd_queue_status(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return

    queue_size = await get_queue_size()
    pending_count = len(pending_news)

    status_text = (
        f"📊 *Статус системы*\n\n"
        f"• 📥 Новостей в очереди: *{queue_size}*\n"
        f"• ⏳ Новостей на модерации: *{pending_count}*\n"
        f"• 👥 Всего админов: *{len(ADMINS)}*\n"
        f"\n*Управление очередью:*\n"
        f"`/postnext` - обработать следующую новость\n"
        f"`/skipnext` - пропустить текущую новость\n"
        f"`/postlatest` - принудительно проверить RSS\n"
        f"\n*Добавление лент:*\n"
        f"`/addsite <url>` - добавить RSS\n"
        f"`/listsites` - посмотреть ленты"
    )

    await message.answer(status_text, parse_mode="Markdown")


@dp.message(Command("postnext"))
async def cmd_post_next(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return

    # Запускаем обработку следующей новости из очереди
    from parser import process_next_from_queue
    success = await process_next_from_queue()

    if success:
        await message.answer("✅ Следующая новость отправлена на первичную модерацию всем админам!")
    else:
        await message.answer("❌ В очереди нет новых новостей.")


@dp.message(Command("skipnext"))
async def cmd_skip_next(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return

    # Пропускаем текущую новость (очищаем зависшие обработки)
    await clear_stuck_processing()
    await message.answer("✅ Зависшие обработки очищены. Следующая новость будет обработана автоматически.")


@dp.message(Command("postlatest"))
async def cmd_post_latest(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return

    sites = await get_sites()
    if not sites:
        await message.answer("❌ Сайты не добавлены! Используй /addsite")
        return

    await message.answer("🔄 Принудительно проверяю RSS-ленты...")

    posted = 0
    for url in sites:
        from parser import parse_feed_and_process
        try:
            news_count = await parse_feed_and_process(url, limit=1)
            posted += news_count
            if news_count > 0:
                await message.answer(f"✅ Добавлено {news_count} новостей из:\n`{url}`", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ Ошибка при проверке {url}:\n`{e}`", parse_mode="Markdown")

    if posted == 0:
        await message.answer("ℹ️ Новых новостей для публикации нет.")
    else:
        await message.answer(f"🎯 Всего добавлено в очередь: {posted} новостей")


# Обработчик для любых других сообщений
@dp.message()
async def handle_other_messages(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "ℹ️ Используй /help для просмотра всех команд\n"
            "или /start для начала работы"
        )
    else:
        await message.answer("❌ У тебя нет доступа к этому боту.")


# Инициализация базы данных при запуске
async def initialize():
    await init_db()
    print("✅ База данных инициализирована")


# Запуск инициализации
async def on_startup():
    await initialize()


