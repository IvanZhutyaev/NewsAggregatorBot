import asyncio
import feedparser
import requests
import re
import html
from bs4 import BeautifulSoup
from config import DEEPSEEK_KEY
from database import get_sites, is_news_sent, is_news_published, mark_news_sent, add_to_queue, clear_stuck_processing, \
    get_next_from_queue, mark_queue_processed, get_queue_size
from news_sender import send_raw_news_to_admin


# Парсинг полного текста статьи
def get_full_article(url: str) -> str:
    try:

        print(f"🔍 Парсим статью: {url}")

        # Добавляем заголовки чтобы избежать блокировки
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        response = requests.get(url, timeout=4, headers=headers)
        response.encoding = response.apparent_encoding
        print(response.status_code)
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

        article = None
        for selector in selectors:
            found = soup.select(selector)
            if found:
                article = found[0]
                print(f"✅ Найден контент по селектору: {selector}")
                break

        # Если не нашли по селекторам, ищем по структуре
        if not article:
            # Ищем самый большой текстовый блок
            text_blocks = soup.find_all(['div', 'section'])
            text_blocks = [block for block in text_blocks if len(block.get_text(strip=True)) > 200]
            if text_blocks:
                article = max(text_blocks, key=lambda x: len(x.get_text(strip=True)))
                print("✅ Найден контент по размеру текстового блока")

        if article:
            # Удаляем ненужные элементы
            for element in article.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe']):
                element.decompose()

            paragraphs = [p.get_text().strip() for p in article.find_all("p")]
            # Фильтруем пустые и слишком короткие параграфы
            paragraphs = [p for p in paragraphs if len(p) > 30]
            text = "\n\n".join(paragraphs).strip()

            if text:
                print(f"✅ Успешно извлечен текст: {len(text)} символов, {len(text.split())} слов")
                return text
            else:
                print("❌ Текст извлечен, но пустой после фильтрации")
                return ""
        else:
            print("❌ Контент не найден на странице")
            return ""

    except Exception as e:
        print(f"❌ Ошибка парсинга {url}: {e}")
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

async def process_with_deepseek(title: str, body: str) -> str:
    """Обработка текста через DeepSeek после одобрения сырой новости"""
    return paraphrase_with_deepseek(title, body)

# Функция для сравнения текстов до и после обработки
def print_text_comparison(original_title: str, original_body: str, processed_text: str):
    print("\n" + "=" * 80)
    print("📋 СРАВНЕНИЕ ТЕКСТОВ:")
    print("=" * 80)

    print("\n🔹 ИСХОДНЫЙ ЗАГОЛОВОК:")
    print("-" * 40)
    print(original_title)

    print("\n🔹 ИСХОДНЫЙ ТЕКСТ:")
    print("-" * 40)
    if original_body and len(original_body.strip()) > 0:
        print(original_body[:500] + "..." if len(original_body) > 500 else original_body)
        print(f"(Длина: {len(original_body)} символов, {len(original_body.split())} слов)")
    else:
        print("❌ Текст отсутствует")
        print("(Длина: 0 символов, 0 слов)")

    print("\n🔹 ОБРАБОТАННЫЙ ТЕКСТ (DeepSeek):")
    print("-" * 40)
    print(processed_text)
    print(f"(Длина: {len(processed_text)} символов, {len(processed_text.split())} слов)")

    print("\n🔹 СТАТИСТИКА:")
    print("-" * 40)
    original_words = len(original_body.split()) if original_body and len(original_body.strip()) > 0 else 0
    processed_words = len(processed_text.split())

    print(f"Сокращение текста: {original_words} → {processed_words} слов")

    if original_words > 0:
        reduction_percent = ((original_words - processed_words) / original_words * 100)
        print(f"Сокращение: {reduction_percent:.1f}%")
    else:
        print("Сокращение: невозможно вычислить (исходный текст пустой)")

    print("=" * 80 + "\n")



# ДИПСИК
def paraphrase_with_deepseek(title: str, body: str) -> str:
    # Если текст слишком короткий, не используем DeepSeek
    if not body or len(body.strip()) < 80:  # Увеличили порог с 50 до 80
        print(f"⚠️ Текст слишком короткий ({len(body)} символов), используем заголовок")
        result = title
        print_text_comparison(title, body, result)
        return result

    try:
        prompt = f"""
        Ты — профессиональный редактор новостного портала. 
        Перепиши заголовок и текст новости полностью, сохранив факты, но измени формулировки. 

        ‼️ Важно:
        - Делай связанный, читаемый и завершённый текст, даже если в статье только часть. 
        - Объём от 30 до 100 слов.
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
            processed_text = limit_words(text, 180)

            # Выводим сравнение текстов
            print_text_comparison(title, body, processed_text)

            return processed_text
        else:
            print("DeepSeek ERROR:", data)
            fallback_text = limit_words(clean_text(f"{title}\n\n{body}"), 180)
            print_text_comparison(title, body, fallback_text)
            return fallback_text
    except Exception as e:
        print(f"❌ Ошибка DeepSeek: {e}")
        fallback_text = title  # Используем только заголовок при ошибке
        print_text_comparison(title, body, fallback_text)
        return fallback_text


# Обработка новости
async def process_entry(entry):
    title = getattr(entry, "title", "Без названия")
    link = getattr(entry, "link", "")

    print(f"\n🎯 Обрабатываем новость: {title}")
    print(f"🔗 Ссылка: {link}")

    # Сначала получаем описание из RSS (часто там есть краткий текст)
    rss_description = getattr(entry, "summary", getattr(entry, "description", ""))
    if rss_description:
        # Очищаем HTML из описания
        rss_description = clean_text(rss_description)
        print(f"📝 RSS описание: {len(rss_description)} символов")

    # Потом пытаемся получить полный текст статьи
    full_article = get_full_article(link)

    # В parser.py изменить условия:
    if full_article and len(full_article) > 50:  # было 100
        body = full_article
    elif rss_description and len(rss_description) > 30:  # было 50
        body = rss_description
    else:
        # Вместо пустого текста используем заголовок
        body = title

    return paraphrase_with_deepseek(title, body)


# Парсинг фида и обработка новостей
async def parse_feed_and_process(url: str, limit: int = 20) -> int:
    """Парсит RSS и добавляет новости в очередь с ОРИГИНАЛЬНЫМ текстом"""
    feed = feedparser.parse(url)
    added_to_queue = 0

    for entry in feed.entries[:limit]:
        link = getattr(entry, 'link', '')

        # Проверяем, не была ли уже опубликована или отправлена на модерацию
        if not await is_news_published(link) and not await is_news_sent(link):
            print(f"📥 Добавляем новость в очередь: {getattr(entry, 'title', 'Без названия')}")

            # Получаем ОРИГИНАЛЬНЫЙ текст (без DeepSeek обработки)
            title = getattr(entry, 'title', 'Без названия')

            # Получаем оригинальный текст статьи
            rss_description = getattr(entry, "summary", getattr(entry, "description", ""))
            if rss_description:
                rss_description = clean_text(rss_description)

            full_article = get_full_article(link)

            # Выбираем лучший источник текста
            if full_article and len(full_article) > 100:
                original_text = full_article
            elif rss_description and len(rss_description) > 50:
                original_text = rss_description
            else:
                original_text = ""

            # Получаем путь к случайному изображению
            import os
            import random
            image_files = os.listdir("images")
            image_path = os.path.join("images", random.choice(image_files)) if image_files else None

            # Добавляем в очередь ОРИГИНАЛЬНЫЙ текст
            await add_to_queue(link, title, original_text, image_path)
            added_to_queue += 1

            await asyncio.sleep(0.5)

    return added_to_queue

async def process_multiple_from_queue():
    """Обрабатывает новости из очереди с учетом блокировки модерации"""
    from database import is_moderation_locked

    # Проверяем, не заблокирована ли модерация
    if await is_moderation_locked():
        print("⏳ Модерация заблокирована - ждем завершения текущей новости")
        return 0

    queue_size = await get_queue_size()
    if queue_size == 0:
        return 0

    # Берем только одну новость вместо нескольких
    success = await process_next_from_queue()
    return 1 if success else 0
# Проверка новостей и отправка админу
async def check_news_and_send():
    sites = await get_sites()
    for url in sites:
        await parse_feed_and_process(url, limit=5)


async def process_next_from_queue():
    """Обрабатывает следующую новость из очереди - отправляет ОРИГИНАЛЬНЫЙ текст"""
    try:
        await clear_stuck_processing()
        queue_item = await get_next_from_queue()

        if not queue_item:
            return False

        queue_id, link, title, news_text, image_path = queue_item

        print(f"🎯 Обрабатываем новость из очереди: {title}")
        print(f"🔗 Ссылка: {link}")

        # Проверяем, не была ли уже отправлена на модерацию
        if await is_news_sent(link):
            print(f"⚠️ Новость уже отправлена на модерацию, пропускаем: {link}")
            await mark_queue_processed(link)
            return False

        # Отправляем СЫРУЮ (оригинальную) новость на первичное одобрение БЕЗ ФОТО
        await send_raw_news_to_admin(title, news_text, link)

        # Помечаем как отправленную на модерацию
        await mark_news_sent(link)

        # Удаляем из очереди после успешной обработки
        await mark_queue_processed(link)

        print(f"✅ Сырая новость отправлена на первичную модерацию")
        return True

    except Exception as e:
        print(f"❌ Ошибка обработки новости из очереди: {e}")
        if 'queue_item' in locals() and queue_item:
            await mark_queue_processed(queue_item[1])
        return False
async def process_with_deepseek(title: str, body: str) -> str:
    """Обработка текста через DeepSeek после одобрения сырой новости"""
    return paraphrase_with_deepseek(title, body)
# Фоновая проверка
async def scheduler():
    """Улучшенный планировщик с блокировкой модерации"""
    print("🔄 Планировщик парсера запущен!")

    while True:
        try:
            # Проверяем новые новости
            sites = await get_sites()
            if not sites:
                print("⚠️ Нет RSS-лент для проверки. Используйте /addsite")
                await asyncio.sleep(60)
                continue

            print(f"🔍 Проверяем {len(sites)} RSS-лент...")

            total_added = 0
            for url in sites:
                try:
                    added = await parse_feed_and_process(url, limit=15)
                    total_added += added
                    print(f"✅ Добавлено {added} новостей из {url}")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"❌ Ошибка парсинга {url}: {e}")

            if total_added > 0:
                print(f"🎯 Всего добавлено в очередь: {total_added} новостей")
            else:
                print("ℹ️ Новых новостей не найдено")

            # Обрабатываем очередь ТОЛЬКО если модерация не заблокирована
            from database import is_moderation_locked
            if not await is_moderation_locked():
                queue_size = await get_queue_size()
                if queue_size > 0:
                    print(f"📥 Обрабатываем очередь: {queue_size} новостей")
                    processed = await process_multiple_from_queue()
                    print(f"✅ Обработано {processed} новостей из очереди")
                else:
                    print("📭 Очередь пуста")
            else:
                print("⏳ Модерация заблокирована - пропускаем обработку очереди")

            # Пауза перед следующим циклом
            print("⏳ Следующая проверка через 30 секунд...")
            await asyncio.sleep(30)

        except Exception as e:
            print(f"❌ Ошибка в планировщике: {e}")
            print("⏳ Повторная попытка через 60 секунд...")
            await asyncio.sleep(60)

