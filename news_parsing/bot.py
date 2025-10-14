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
from database import init_db, add_site, remove_site, get_sites, is_news_sent, mark_news_sent
from site_poster import post_news_to_site
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Глобальный словарь для хранения новостей в ожидании
pending_news = {}

# Отправка новости админам
async def send_news_to_admin(news_text: str, source_url: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            image_files = os.listdir("images")
            if not image_files:
                print("❌ Нет изображений в папке images")
                return

            image_path = os.path.join("images", random.choice(image_files))
            news_id = hashlib.md5(source_url.encode()).hexdigest()
            pending_news[news_id] = {"url": source_url, "image": image_path, "text": news_text}

            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🌐 На сайт", callback_data=f"site|{news_id}")
            keyboard.button(text="✅ В Telegram", callback_data=f"approve|{news_id}")
            keyboard.button(text="🚀 Оба", callback_data=f"both|{news_id}")
            keyboard.button(text="❌ Отклонить", callback_data=f"reject|{news_id}")

            photo = FSInputFile(image_path)
            admin_caption = f"{news_text}\n\nИсточник: {source_url}"

            for admin_id in ADMINS:
                try:
                    if len(admin_caption) <= 1024:
                        await bot.send_photo(
                            admin_id,
                            photo,
                            caption=admin_caption,
                            reply_markup=keyboard.as_markup()
                        )
                    else:
                        await bot.send_photo(admin_id, photo, reply_markup=keyboard.as_markup())
                        await bot.send_message(admin_id, admin_caption)
                    print(f"✅ Новость отправлена админу {admin_id}")
                except TelegramForbiddenError:
                    print(f"❌ Не удалось отправить админу {admin_id} — он не написал боту.")
                except Exception as e:
                    print(f"❌ Ошибка отправки админу {admin_id}: {e}")

            break  # Успешно отправлено, выходим из цикла повторных попыток

        except TelegramNetworkError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Экспоненциальная задержка
                print(f"⚠️ Ошибка сети, повторная попытка {attempt + 1} через {wait_time} сек...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ Не удалось отправить новость после {max_retries} попыток: {e}")
        except Exception as e:
            print(f"❌ Критическая ошибка в send_news_to_admin: {e}")
            break

# Подтверждение новости
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

    # Полный текст
    caption = news_text

    try:
        await bot.send_photo(CHANNEL_ID, photo, caption=caption, parse_mode="HTML")
    except Exception as e:
        print("❌ Ошибка отправки в канал:", e)
        await callback.message.answer("❌ Не удалось отправить новость в канал.")
        return

    await mark_news_sent(data["url"])
    pending_news.pop(news_id, None)

    try:
        await callback.message.delete()
    except Exception:
        pass

    # уведомляем админов
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, "✅ Новость опубликована.")
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
            await mark_news_sent(data["url"])
            pending_news.pop(news_id, None)
            await callback.message.answer("🌐 Новость опубликована на сайте!")
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
        if success_site and success_tg:
            await mark_news_sent(data["url"])
            pending_news.pop(news_id, None)
            await callback.message.answer("🚀 Новость опубликована в Telegram и на сайте!")
        else:
            await callback.message.answer("⚠️ Ошибка при публикации (проверь лог).")
    except Exception as e:
        print(f"❌ Ошибка в post_to_both: {e}")
        await callback.message.answer("❌ Произошла ошибка при публикации.")
# Отклонение новости
@dp.callback_query(F.data.startswith("reject|"))
async def reject_news(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

    _, news_id = callback.data.split("|", 1)
    pending_news.pop(news_id, None)

    try:
        await callback.message.delete()
        for admin_id in ADMINS:
            await bot.send_message(admin_id, "❌ Новость отклонена.")
    except Exception:
        pass

# Команды для админов
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

@dp.message(Command("start"))
async def cmd_start(message):
    if not is_admin(message.from_user.id):
        await message.answer("Ты не админ!")
        return
    await message.answer(
        "Привет, админ! Команды:\n"
        "/addsite <url>\n"
        "/listsites\n"
        "/removesite <url>\n"
        "/postlatest"
    )

@dp.message(Command("addsite"))
async def cmd_add_site(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажи ссылку на RSS")
        return
    await add_site(args[1])
    await message.answer(f"Сайт {args[1]} добавлен!")

@dp.message(Command("listsites"))
async def cmd_list_sites(message):
    if not is_admin(message.from_user.id):
        return
    sites = await get_sites()
    if not sites:
        await message.answer("Сайты не добавлены")
    else:
        await message.answer("\n".join(sites))

@dp.message(Command("removesite"))
async def cmd_remove_site(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажи ссылку на RSS для удаления")
        return
    await remove_site(args[1])
    await message.answer(f"Сайт {args[1]} удалён!")

@dp.message(Command("postlatest"))
async def cmd_post_latest(message):
    if not is_admin(message.from_user.id):
        await message.answer("Ты не админ!")
        return
    sites = await get_sites()
    if not sites:
        await message.answer("Сайты не добавлены!")
        return
    posted = 0
    for url in sites:
        from parser import parse_feed_and_process
        news_count = await parse_feed_and_process(url, limit=1)
        posted += news_count
    if posted == 0:
        await message.answer("Новых новостей для публикации нет.")
    else:
        await message.answer(f"Отправлено {posted} новостей на проверку.")