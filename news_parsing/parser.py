import asyncio
import feedparser
import requests
import re
import html
from bs4 import BeautifulSoup
from config import DEEPSEEK_KEY
from database import get_sites, is_news_sent, is_news_published, mark_news_sent, add_to_queue, clear_stuck_processing, \
    get_next_from_queue, mark_queue_processed, get_queue_size
from bot import send_original_news_to_admin


# Парсинг полного текста статьи
def get_full_article(url: str) -> str:
    try:
        print(f"🔍 Парсим статью: {url}")

        # Добавляем заголовки чтобы избежать блокировки
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, timeout=10, headers=headers)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        # Расширенный список селекторов для поиска контента
        selectors = [
            "article",
            "div.article",
            "div.content",
            "div.post-content",
            "div.entry-content",
            "div.story-text",
            "div.text",
            "main",
            "[role='main']",
            "div.news-text",
            "div.news-content",
            "div.news-detail",
            "div.detail-text",
            ".news__text",
            ".article__text",
            ".content__text",
            "div.news-body",
            "div.article-body"
        ]

        # Ищем контент по селекторам
        content = None
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                print(f"✅ Найден контент по селектору: {selector}")
                break

        # Если не нашли по селекторам, пробуем найти по классам содержащим "content", "text", "article"
        if not content:
            for tag in soup.find_all(['div', 'article', 'section']):
                classes = tag.get('class', [])
                if classes and any(keyword in ' '.join(classes).lower() for keyword in
                                  ['content', 'text', 'article', 'story', 'post', 'entry', 'body', 'main']):
                    content = tag
                    print(f"✅ Найден контент по классу: {classes}")
                    break

        # Если все еще не нашли, берем body
        if not content:
            content = soup.find('body')
            print("⚠️ Контент не найден, используем body")

        # Очищаем контент от ненужных элементов
        if content:
            # Удаляем ненужные элементы
            for element in content.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe']):
                element.decompose()

            # Удаляем элементы с классами содержащими "menu", "header", "footer", "sidebar", "ad", "banner"
            for element in content.find_all(class_=re.compile(
                    r'menu|header|footer|sidebar|ad|banner|social|comment|meta|related|popular', re.I)):
                element.decompose()

            # Извлекаем текст
            text = content.get_text(separator='\n', strip=True)

            # Очищаем текст от лишних переносов и пробелов
            text = re.sub(r'\n\s*\n', '\n\n', text)
            text = re.sub(r' +', ' ', text)

            # Обрезаем до разумной длины (примерно 2000 символов)
            if len(text) > 2000:
                text = text[:2000] + "..."

            return text.strip()

        return ""

    except Exception as e:
        print(f"❌ Ошибка парсинга статьи {url}: {e}")
        return ""


# Скачивание изображения
def download_image(url: str) -> str:
    try:
        print(f"📥 Скачиваем изображение: {url}")

        # Пропускаем пустые URL
        if not url or url.strip() == "":
            print("❌ Пустой URL изображения")
            return ""

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()

        # Проверяем, что это изображение
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            print(f"❌ Неверный content-type: {content_type}")
            return ""

        # Создаем папку для изображений если её нет
        import os
        if not os.path.exists("images"):
            os.makedirs("images")

        # Генерируем имя файла
        import hashlib
        file_ext = ".jpg"  # по умолчанию
        if 'jpeg' in content_type or 'jpg' in content_type:
            file_ext = ".jpg"
        elif 'png' in content_type:
            file_ext = ".png"
        elif 'gif' in content_type:
            file_ext = ".gif"
        elif 'webp' in content_type:
            file_ext = ".webp"

        filename = f"images/{hashlib.md5(url.encode()).hexdigest()}{file_ext}"

        # Сохраняем файл
        with open(filename, "wb") as f:
            f.write(response.content)

        print(f"✅ Изображение сохранено: {filename}")
        return filename

    except Exception as e:
        print(f"❌ Ошибка скачивания изображения {url}: {e}")
        return ""


# Обработка через DeepSeek
def paraphrase_with_deepseek(title: str, text: str) -> str:
    try:
        import requests

        headers = {
            "Authorization": f"Bearer {DEEPSEK_KEY}",
            "Content-Type": "application/json"
        }

        prompt = f"""
Перепиши эту новость своими словами, сохраняя основной смысл и ключевые факты. Сделай текст более живым и интересным для читателя.

Оригинальный заголовок: {title}

Текст новости:
{text}

Требования к результату:
1. Напиши новый привлекательный заголовок
2. Перескажи текст своими словами, сохраняя все важные детали
3. Сделай текст более читабельным и структурированным
4. Сохрани тон новостной статьи
5. Не добавляй лишней информации, которой нет в оригинале

Верни результат в формате:
ЗАГОЛОВОК

Текст новости...
        """

        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=data, timeout=30)
        response.raise_for_status()

        result = response.json()
        processed_text = result["choices"][0]["message"]["content"].strip()

        print("✅ Текст обработан через DeepSeek")
        return processed_text

    except Exception as e:
        print(f"❌ Ошибка DeepSeek: {e}")
        # Возвращаем оригинал в случае ошибки
        return f"{title}\n\n{text}"


# Парсинг RSS и добавление в очередь
async def parse_feed_and_process(url: str, limit: int = 5) -> int:
    try:
        print(f"📡 Парсим RSS: {url}")

        feed = feedparser.parse(url)
        if feed.entries is None or len(feed.entries) == 0:
            print(f"❌ В RSS-ленте нет записей: {url}")
            return 0

        added_count = 0
        for entry in feed.entries[:limit]:
            try:
                link = entry.get("link", "").strip()
                if not link:
                    continue

                # Проверяем, не отправляли ли уже эту новость
                if await is_news_sent(link) or await is_news_published(link):
                    continue

                # Получаем заголовок
                title = html.unescape(entry.get("title", "Без заголовка")).strip()

                # Получаем описание
                summary = html.unescape(entry.get("summary", "")).strip()

                # Если описания нет или оно короткое, парсим полную статью
                if not summary or len(summary) < 200:
                    full_text = get_full_article(link)
                    if full_text:
                        summary = full_text
                    elif hasattr(entry, 'content') and entry.content:
                        # Пробуем получить контент из поля content
                        content_text = ""
                        for content in entry.content:
                            if hasattr(content, 'value'):
                                content_text += html.unescape(content.value) + "\n"
                        summary = content_text.strip()

                # Если все еще нет текста, используем заголовок
                if not summary:
                    summary = title

                # Получаем изображение
                image_url = ""

                # Ищем в медиа-контенте
                if hasattr(entry, 'media_content') and entry.media_content:
                    for media in entry.media_content:
                        if media.get('type', '').startswith('image/'):
                            image_url = media.get('url', '')
                            if image_url:
                                break

                # Ищем в enclosure
                if not image_url and hasattr(entry, 'enclosures') and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.get('type', '').startswith('image/'):
                            image_url = enc.get('href', '')
                            if image_url:
                                break

                # Ищем в описании
                if not image_url and summary:
                    soup = BeautifulSoup(summary, "html.parser")
                    img_tag = soup.find("img")
                    if img_tag and img_tag.get("src"):
                        image_url = img_tag["src"]

                # Скачиваем изображение
                image_path = ""
                if image_url:
                    image_path = download_image(image_url)

                # Добавляем в очередь обработки
                await add_to_queue(
                    link=link,
                    title=title,
                    news_text=summary,
                    image_path=image_path,
                    original_title=title,
                    original_text=summary
                )

                # Отмечаем как отправленную на модерацию
                await mark_news_sent(link)

                print(f"✅ Добавлено в очередь: {title[:50]}...")
                added_count += 1

            except Exception as e:
                print(f"❌ Ошибка обработки записи: {e}")
                continue

        print(f"✅ Добавлено {added_count} новостей из {url}")
        return added_count

    except Exception as e:
        print(f"❌ Ошибка парсинга RSS {url}: {e}")
        return 0


# Обработка следующей новости из очереди
async def process_next_from_queue() -> bool:
    try:
        # Получаем следующую новость из очереди
        news = await get_next_from_queue()
        if not news:
            print("ℹ️ В очереди нет новостей для обработки")
            return False

        news_id, link, title, news_text, image_path, original_title, original_text, needs_deepseek, deepseek_processed = news

        print(f"📨 Обрабатываем новость из очереди: {title[:50]}...")

        # Отправляем оригинальную новость на первичную модерацию
        await send_original_news_to_admin(
            original_title=original_title,
            original_text=original_text,
            source_url=link,
            image_path=image_path
        )

        print(f"✅ Оригинальная новость отправлена на первичную модерацию: {link}")
        return True

    except Exception as e:
        print(f"❌ Ошибка в process_next_from_queue: {e}")
        return False


# Автоматическая обработка очереди
async def process_queue_automatically():
    try:
        # Очищаем зависшие обработки
        await clear_stuck_processing()

        # Проверяем размер очереди
        queue_size = await get_queue_size()
        if queue_size == 0:
            return

        print(f"🔄 Автоматически обрабатываем очередь ({queue_size} новостей)")

        # Обрабатываем до 3 новостей за раз
        for _ in range(min(3, queue_size)):
            success = await process_next_from_queue()
            if not success:
                break
            # Ждем между обработками
            await asyncio.sleep(2)

    except Exception as e:
        print(f"❌ Ошибка в автоматической обработке очереди: {e}")


# Периодическая проверка RSS
async def periodic_rss_check():
    try:
        sites = await get_sites()
        if not sites:
            print("ℹ️ Нет RSS-лент для проверки")
            return

        print(f"🔄 Периодическая проверка {len(sites)} RSS-лент...")

        total_added = 0
        for url in sites:
            try:
                added = await parse_feed_and_process(url, limit=2)  # Берем по 2 новости с каждой ленты
                total_added += added
                # Ждем между запросами к разным сайтам
                await asyncio.sleep(3)
            except Exception as e:
                print(f"❌ Ошибка проверки {url}: {e}")
                continue

        if total_added > 0:
            print(f"🎯 Всего добавлено в очередь: {total_added} новостей")

            # Запускаем обработку очереди если есть новые новости
            await process_queue_automatically()

    except Exception as e:
        print(f"❌ Ошибка в periodic_rss_check: {e}")
