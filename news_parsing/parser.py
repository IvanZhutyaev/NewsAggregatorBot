import asyncio
import feedparser
import requests
import re
import html
from bs4 import BeautifulSoup
from config import DEEPSEEK_KEY
from database import get_sites, is_news_sent
from bot import send_news_to_admin


# Парсинг полного текста статьи
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


# Очистка HTML и мусора
def clean_text(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)  # удаляем все HTML-теги
    text = html.unescape(text)  # заменяем HTML-сущности на символы
    text = re.sub(r'\s+\n', '\n', text)  # убираем лишние пробелы перед переносами
    text = re.sub(r'\n{3,}', '\n\n', text)  # максимум 2 переноса подряд
    return text.strip()


# Ограничение текста
def limit_words(text: str, max_words: int = 180) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


# ДИПСИК
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


# Обработка новости
async def process_entry(entry):
    title = getattr(entry, "title", "Без названия")
    link = getattr(entry, "link", "")
    body = get_full_article(link)
    if not body:
        body = getattr(entry, "summary", getattr(entry, "description", ""))
    return paraphrase_with_deepseek(title, body)


# Парсинг фида и обработка новостей
async def parse_feed_and_process(url: str, limit: int = 5) -> int:
    feed = feedparser.parse(url)
    processed_count = 0

    for entry in feed.entries[:limit]:
        link = getattr(entry, "link", "")
        if not await is_news_sent(link):
            news_text = await process_entry(entry)
            await send_news_to_admin(news_text, link)
            processed_count += 1
            await asyncio.sleep(1)

    return processed_count


# Проверка новостей и отправка админу
async def check_news_and_send():
    sites = await get_sites()
    for url in sites:
        await parse_feed_and_process(url, limit=5)


# Фоновая проверка
async def scheduler():
    while True:
        await check_news_and_send()
        await asyncio.sleep(600)