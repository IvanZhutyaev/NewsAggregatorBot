import os
import requests
import json
from datetime import datetime
from config import SITE_URL, SITE_LOGIN, SITE_PASSWORD


# Базовый URL API
BASE_API_URL = "https://api.demo.agrosearch.kz/api"
# BASE_API_URL = "https://api.agrosearch.kz/api"  # для продакшена

# Глобальная переменная для хранения токена
access_token = None


def truncate_text(text: str, max_length: int) -> str:
    """Обрезает текст до максимальной длины, сохраняя целые предложения"""
    if not text or len(text) <= max_length:
        return text

    # Находим конец первого предложения
    sentence_endings = ['.', '!', '?', '。', '！', '？']

    # Ищем конец первого предложения в пределах max_length
    for i in range(min(len(text), max_length)):
        if text[i] in sentence_endings:
            # Проверяем, что после точки пробел или конец текста
            if i + 1 >= len(text) or text[i + 1] in [' ', '\n', '\r']:
                return text[:i + 1]

    # Если не нашли конец предложения, ищем ближайший пробел
    last_space = text.rfind(' ', 0, max_length - 3)
    if last_space > 0:
        return text[:last_space] + "..."

    return text[:max_length - 3] + "..."


def login_to_api() -> bool:
    """Аутентификация в API и получение токена"""
    global access_token

    login_url = f"{BASE_API_URL}/auth/login"

    try:
        print("🔑 Аутентифицируемся в API...")

        payload = {
            "email": SITE_LOGIN,
            "password": SITE_PASSWORD
        }

        headers = {
            "Content-Type": "application/json",
            "Accept-Language": "ru"
        }

        response = requests.post(login_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            if access_token:
                print("✅ Успешная аутентификация в API")
                return True
            else:
                print("❌ Токен не получен в ответе")
                return False
        else:
            print(f"❌ Ошибка аутентификации: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Ошибка при аутентификации: {e}")
        return False


def upload_image(image_path: str) -> str:
    """Загружает изображение и возвращает путь для использования в новости"""
    global access_token

    if not access_token:
        if not login_to_api():
            return None

    upload_url = f"{BASE_API_URL}/upload/image"

    try:
        print(f"🖼️ Загружаем изображение: {image_path}")

        if not os.path.exists(image_path):
            print(f"❌ Файл изображения не найден: {image_path}")
            return None

        with open(image_path, 'rb') as image_file:
            files = {'image': (os.path.basename(image_path), image_file, 'image/jpeg')}

            response = requests.post(upload_url, files=files, timeout=30)

            if response.status_code == 200:
                data = response.json()
                image_path_from_api = data.get("data", {}).get("path", "")

                print(f"✅ Изображение загружено, путь от API: {image_path_from_api}")

                # Обрабатываем путь от API - добавляем префикс tmp/images/ если его нет
                if image_path_from_api.startswith("/storage/"):
                    image_path_from_api = image_path_from_api[9:]  # удаляем "/storage/"
                elif image_path_from_api.startswith("https://"):
                    # Если вернулся полный URL, извлекаем только имя файла
                    from urllib.parse import urlparse
                    parsed_url = urlparse(image_path_from_api)
                    filename = os.path.basename(parsed_url.path)
                    image_path_from_api = f"tmp/images/{filename}"
                else:
                    # Если вернулось только имя файла, добавляем путь
                    image_path_from_api = f"tmp/images/{image_path_from_api}"

                print(f"✅ Обработанный путь для image_uri: {image_path_from_api}")
                return image_path_from_api
            else:
                print(f"❌ Ошибка загрузки изображения: {response.status_code}")
                print(f"Ответ: {response.text}")
                return None

    except Exception as e:
        print(f"❌ Ошибка при загрузке изображения: {e}")
        return None


def translate_news_content(title: str, body: str) -> dict:
    """
    Возвращает контент только на русском языке (без перевода)
    """
    # Убедимся, что body не пустой
    if not body or len(body.strip()) == 0:
        body = title  # Используем заголовок как тело если тело пустое

    # Создаем короткий подзаголовок из первых 200 символов тела текста
    short_subtitle = truncate_text(body, 200)

    translations = {
        'ru': {
            'title': truncate_text(title, 255),
            'description': body,
            'subtitle': short_subtitle
        },
        'kk': {
            'title': truncate_text(title, 255),
            'description': body,
            'subtitle': short_subtitle
        },
        'en': {
            'title': truncate_text(title, 255),
            'description': body,
            'subtitle': short_subtitle
        },
        'zh': {
            'title': truncate_text(title, 255),
            'description': body,
            'subtitle': short_subtitle
        }
    }

    print(f"✅ Контент подготовлен: заголовок {len(title)} симв., описание {len(body)} симв.")
    return translations

def extract_title_and_body(text: str):
    """Разделяет текст на заголовок и тело"""
    text = text.strip()

    # Если текст пустой, возвращаем заголовок как тело
    if not text:
        return "Новость", "Содержание новости"

    # Ищем разделитель - двойной перенос строки
    if "\n\n" in text:
        parts = text.split("\n\n", 1)
        title = parts[0].strip()
        body = parts[1].strip()
    else:
        # Ищем первый одинарный перенос строки
        lines = text.split("\n")
        if len(lines) > 1:
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
        else:
            # Только одна строка - используем как заголовок, а тело делаем из заголовка
            title = text
            body = text  # Используем тот же текст как тело

    # Ограничиваем длину заголовка
    title = truncate_text(title, 255)

    # Если тело пустое, используем заголовок
    if not body:
        body = title

    print(f"📄 Извлечен заголовок ({len(title)} символов): {title}")
    print(f"📄 Извлечен текст ({len(body)} символов): {body[:100]}...")

    return title, body


def create_news_api(title: str, description: str, subtitle: str, image_uri: str, translations: dict) -> bool:
    """Создает новость через API только на русском языке"""
    global access_token

    if not access_token:
        if not login_to_api():
            return False

    news_url = f"{BASE_API_URL}/content/news"

    try:
        print("📤 Создаем новость через API (только русский язык)...")

        # Проверяем обязательные поля
        if not translations['ru']['title'] or not translations['ru']['description']:
            print("❌ Ошибка: заголовок или описание пустые")
            return False

        # SEO настройки только на русском
        seo_keywords = truncate_text("агро, сельское хозяйство, АПК, новости сельского хозяйства", 255)

        # Упрощенный payload только с русскими полями
        payload = {
            # Основные поля на русском
            "title": translations['ru']['title'],
            "description": translations['ru']['description'],
            "subtitle": translations['ru']['subtitle'],
            "image_uri": image_uri,

            # Остальные языки используем те же русские данные
            "title_kk": translations['ru']['title'],
            "description_kk": translations['ru']['description'],
            "subtitle_kk": translations['ru']['subtitle'],

            "title_en": translations['ru']['title'],
            "description_en": translations['ru']['description'],
            "subtitle_en": translations['ru']['subtitle'],

            "title_zh": translations['ru']['title'],
            "description_zh": translations['ru']['description'],
            "subtitle_zh": translations['ru']['subtitle'],

            # SEO поля (все на русском)
            "seo_title": truncate_text(translations['ru']['title'], 255),
            "seo_description": truncate_text(translations['ru']['subtitle'], 500),
            "seo_keywords": seo_keywords,
            "seo_image": image_uri,

            "seo_title_kk": truncate_text(translations['ru']['title'], 255),
            "seo_description_kk": truncate_text(translations['ru']['subtitle'], 500),
            "seo_keywords_kk": seo_keywords,

            "seo_title_en": truncate_text(translations['ru']['title'], 255),
            "seo_description_en": truncate_text(translations['ru']['subtitle'], 500),
            "seo_keywords_en": seo_keywords,

            "seo_title_zh": truncate_text(translations['ru']['title'], 255),
            "seo_description_zh": truncate_text(translations['ru']['subtitle'], 500),
            "seo_keywords_zh": seo_keywords,

            # Дополнительные поля
            "date_publication": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept-Language": "ru"
        }

        print(f"📊 Отправляем данные (только русский язык):")
        print(f"   Заголовок: '{payload['title']}' ({len(payload['title'])} симв.)")
        print(f"   Подзаголовок: '{payload['subtitle']}' ({len(payload['subtitle'])} симв.)")
        print(f"   Описание: '{payload['description'][:100]}...' ({len(payload['description'])} симв.)")
        print(f"   Image URI: '{payload['image_uri']}'")
        print(f"   URL: {news_url}")
        print(f"   Токен: {access_token[:20]}...")

        response = requests.post(news_url, json=payload, headers=headers, timeout=30)

        print(f"📡 Ответ сервера: {response.status_code}")
        print(f"📡 Заголовки ответа: {dict(response.headers)}")

        # Проверяем тип ответа
        content_type = response.headers.get('content-type', '')
        if 'application/json' in content_type:
            response_data = response.json()
            print(f"📡 JSON ответ: {response_data}")
        else:
            print(f"📡 Не-JSON ответ (первые 200 символов): {response.text[:200]}")

        if response.status_code == 201:
            result_data = response.json()
            print("✅ Новость успешно создана через API (только русский язык)!")
            print(f"🎉 ID новости: {result_data.get('data', {}).get('id', 'N/A')}")
            return True
        else:
            print(f"❌ Ошибка создания новости: {response.status_code}")

            if response.status_code == 401:
                print("🔄 Токен устарел, пробуем переаутентифицироваться...")
                if login_to_api():
                    headers["Authorization"] = f"Bearer {access_token}"
                    response = requests.post(news_url, json=payload, headers=headers, timeout=30)
                    if response.status_code == 201:
                        print("✅ Новость успешно создана после переаутентификации!")
                        return True

            return False

    except Exception as e:
        print(f"❌ Ошибка при создании новости: {e}")
        import traceback
        traceback.print_exc()
        return False


def post_news_to_site(news_text: str, image_path: str = None) -> bool:
    """Основная функция публикации новости через API (только русский язык)"""

    # Шаг 1: Аутентификация
    if not login_to_api():
        print("❌ Не удалось аутентифицироваться в API")
        return False

    # Шаг 2: Извлечение заголовка и текста
    title, body = extract_title_and_body(news_text)

    # ВРЕМЕННАЯ ПРОВЕРКА: если тело пустое, используем тестовый текст
    if not body or len(body.strip()) == 0:
        print("⚠️ Тело новости пустое, используем тестовый текст")
        body = "Это тестовое описание новости. " + title

    # Шаг 3: Загрузка изображения
    image_uri = None
    if image_path and os.path.exists(image_path):
        image_uri = upload_image(image_path)
        if not image_uri:
            print("⚠️ Продолжаем без изображения")
    else:
        print("⚠️ Путь к изображению не указан или файл не существует")

    # Шаг 4: Подготовка контента (без перевода)
    print("🔄 Подготавливаем контент (только русский язык)...")
    translations = translate_news_content(title, body)

    # Шаг 5: Создание новости
    subtitle = truncate_text(body, 200)
    success = create_news_api(title, body, subtitle, image_uri, translations)

    if success:
        print("🎉 Новость успешно опубликована на сайте (только русский язык)!")
    else:
        print("❌ Не удалось опубликовать новость на сайте")

    return success

def post_news_to_site_simple(news_text: str, image_path: str = None) -> bool:
    """Простая версия публикации (только русский язык)"""

    if not login_to_api():
        return False

    title, body = extract_title_and_body(news_text)

    image_uri = None
    if image_path and os.path.exists(image_path):
        image_uri = upload_image(image_path)

    # Создаем минимальные переводы (только русский)
    short_subtitle = truncate_text(body, 200)
    translations = {
        'ru': {
            'title': title,
            'description': body,
            'subtitle': short_subtitle
        },
        'kk': {
            'title': title,
            'description': body,
            'subtitle': short_subtitle
        },
        'en': {
            'title': title,
            'description': body,
            'subtitle': short_subtitle
        },
        'zh': {
            'title': title,
            'description': body,
            'subtitle': short_subtitle
        }
    }

    return create_news_api(title, body, short_subtitle, image_uri, translations)


# Функции для обратной совместимости
def login_to_site() -> bool:
    """Старая функция для обратной совместимости"""
    return login_to_api()


def get_csrf_token_for_create() -> str:
    """Заглушка для обратной совместимости"""
    return ""


def check_required_fields():
    """Заглушка для обратной совместимости"""
    return []
