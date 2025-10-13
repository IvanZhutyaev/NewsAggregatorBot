import asyncio
import feedparser
import requests
import os
import random
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import BOT_TOKEN, CHANNEL_ID, DEEPSEEK_KEY, ADMINS
from database import init_db, add_site, remove_site, get_sites, is_news_sent, mark_news_sent
from aiogram.exceptions import TelegramForbiddenError
import hashlib
import html
import re

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

#Глобальный словарь для хранения новостей в ожидании
pending_news = {}


#Парсинг полного текста статьи
def get_full_article(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        article = soup.find("article") or soup.find("div", class_="article") or soup.find("div", class_="content")
        if article:
            paragraphs = [p.get_text() for p in article.find_all("p")]
            text = "\n\n".join(paragraphs).strip()
            return text
        else:
            return ""
    except Exception as e:
        print("Ошибка парсинга:", e)
        return ""


#Очистка HTML и мусора ЭТО НЕ РАБТАЕТ
def clean_text(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)  # удаляем все HTML-теги
    text = html.unescape(text)  # заменяем HTML-сущности на символы
    text = re.sub(r'\s+\n', '\n', text)  # убираем лишние пробелы перед переносами
    text = re.sub(r'\n{3,}', '\n\n', text)  # максимум 2 переноса подряд
    return text.strip()


#Ограничение текста
def limit_words(text: str, max_words: int = 180) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


#ДИПСИК
def paraphrase_with_deepseek(title: str, body: str) -> str:
    try:
        prompt = f"""
        Ты — профессиональный редактор новостного портала. 
        Перепиши заголовок и текст новости полностью, сохранив факты, но измени формулировки. 

        ‼️ Важно:
        - Делай связанный, читаемый и завершённый текст, даже если в статье только часть. 
        - Объём от 40 до 60 слов.
        - НЕ используй никакие кастомизации Telegram (жирный, курсив, ссылки, Эмодзи можно).
        - Не добавляй рекламу и фразы вроде "Читать далее".
        - Делай красивые абзацы, которые удобно читать в Телеграме.
        - Структурируй текст: сначала проблема/событие, затем причины, последствия и прогноз.
        - Сохраняй и подчёркивай конкретику: даты, цифры, проценты, имена, суммы.
        - Пиши ясным, живым литературным стилем, как для деловой аудитории.
        - Ни в коем случае не используй в текст звездочки "*"
        - Не пиши "Заголовок: Бла бла, Текст: Бла Бла Бла" - Пиши сразу Заголовок И через пустую строку текст
        - Ни в коем случае не добовляй смайлики
        - Убирай все упоминания первоисточника, например убирай "подготовил, написанно для, и тд"
        - Делай одну или несколько пустых строк в новости, что бы немного отделить инфоормацию и она читалась удобнее

        Заголовок: {title}
        Текст: {body}
        """
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Ты — редактор новостного портала."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            message = data["choices"][0].get("message", {})
            text = message.get("content", "")
            text = clean_text(text)
            return limit_words(text, 180)
        else:
            print("DeepSeek ERROR:", data)
            return limit_words(clean_text(f"{title}\n\n{body}"), 180)
    except Exception as e:
        print("Ошибка DeepSeek:", e)
        return limit_words(clean_text(f"{title}\n\n{body}"), 180)


#Отправка новости админамшкгупмшукгрпйшщгрсука
async def send_news_to_admin(news_text: str, source_url: str):
    image_files = os.listdir("images")
    image_path = os.path.join("images", random.choice(image_files))
    news_id = hashlib.md5(source_url.encode()).hexdigest()
    pending_news[news_id] = {"url": source_url, "image": image_path, "text": news_text}

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Подтвердить", callback_data=f"approve|{news_id}")
    keyboard.button(text="❌ Отклонить", callback_data=f"reject|{news_id}")

    from aiogram.types import FSInputFile
    photo = FSInputFile(image_path)

    #текст для flvbyjd новость + ссылка
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
                #фпто без подписи
                await bot.send_photo(admin_id, photo, reply_markup=keyboard.as_markup())
                #потом длиный текст отдельным сообщением
                await bot.send_message(admin_id, admin_caption, parse_mode="HTML")
        except TelegramForbiddenError:
            print(f"❌ Не удалось отправить админу {admin_id} — он не написал боту.")


#Подтверждение новости
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

    from aiogram.types import FSInputFile
    photo = FSInputFile(image_path)

    #Полный текст
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

    #уведомляем админов
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, "✅ Новость опубликована.")
        except Exception:
            pass

#Отклонение новости
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


#Обработка новости
async def process_entry(entry):
    title = getattr(entry, "title", "Без названия")
    link = getattr(entry, "link", "")
    body = get_full_article(link)
    if not body:
        body = getattr(entry, "summary", getattr(entry, "description", ""))
    return paraphrase_with_deepseek(title, body)


#Проверка новостей и отправка админу
async def check_news_and_send():
    sites = await get_sites()
    for url in sites:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            link = getattr(entry, "link", "")
            if not await is_news_sent(link):
                news_text = await process_entry(entry)
                await send_news_to_admin(news_text, link)
                await asyncio.sleep(1)


#Команды для админов
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
        feed = feedparser.parse(url)
        if not feed.entries:
            continue
        entry = feed.entries[0]
        link = getattr(entry, "link", "")
        if not await is_news_sent(link):
            news_text = await process_entry(entry)
            await send_news_to_admin(news_text, link)
            posted += 1
    if posted == 0:
        await message.answer("Новых новостей для публикации нет.")
    else:
        await message.answer(f"Отправлено {posted} новостей на проверку.")


#Фоновая проверка
async def scheduler():
    while True:
        await check_news_and_send()
        await asyncio.sleep(600)


# Запуск
async def main():
    print("🤖 Бот запускается...")
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print("⚠️ Ошибка polling:", e)
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
