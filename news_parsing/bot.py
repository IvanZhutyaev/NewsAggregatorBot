import asyncio
import os
import random
import hashlib
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import FSInputFile
from config import BOT_TOKEN, CHANNEL_ID, ADMINS
from database import init_db, add_site, remove_site, get_sites, is_news_sent, mark_news_sent

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Глобальный словарь для хранения новостей в ожидании
pending_news = {}

# Отправка новости админам
async def send_news_to_admin(news_text: str, source_url: str):
    image_files = os.listdir("images")
    image_path = os.path.join("images", random.choice(image_files))
    news_id = hashlib.md5(source_url.encode()).hexdigest()
    pending_news[news_id] = {"url": source_url, "image": image_path, "text": news_text}

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Подтвердить", callback_data=f"approve|{news_id}")
    keyboard.button(text="❌ Отклонить", callback_data=f"reject|{news_id}")

    photo = FSInputFile(image_path)

    # текст для админов: новость + ссылка
    admin_caption = f"{news_text}\n\nИсточник: {source_url}"

    for admin_id in ADMINS:
        try:
            if len(admin_caption) <= 1024:
                await bot.send_photo(
                    admin_id,
                    photo,
                    caption=admin_caption,
                    parse_mode="HTML",
                    reply_markup=keyboard.as_markup()
                )
            else:
                # фото без подписи
                await bot.send_photo(admin_id, photo, reply_markup=keyboard.as_markup())
                # потом длинный текст отдельным сообщением
                await bot.send_message(admin_id, admin_caption, parse_mode="HTML")
        except TelegramForbiddenError:
            print(f"❌ Не удалось отправить админу {admin_id} — он не написал боту.")

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