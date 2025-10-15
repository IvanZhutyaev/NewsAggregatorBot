import os
import requests
import json
from datetime import datetime
from config import SITE_URL, SITE_LOGIN, SITE_PASSWORD
from translator_libre import translate_text

# Базовый URL API
BASE_API_URL = "https://api.demo.agrosearch.kz/api"
# BASE_API_URL = "https://api.agrosearch.kz/api"  # для продакшена

# Глобальная переменная для хранения токена
access_token = None


def truncate_text(text: str, max_length: int) -> str:
    """Обрезает текст до максимальной длины, сохраняя слова"""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - 3].rsplit(' ', 1)[0] + "..."


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
    Переводит все компоненты новости на три языка
    Возвращает словарь с переводами
    """
    # Создаем короткий подзаголовок из первых 200 символов тела текста
    short_subtitle = truncate_text(body, 200)

    translations = {
        'ru': {
            'title': truncate_text(title, 255),
            'description': body,
            'subtitle': short_subtitle
        }
    }

    # Языки для перевода
    target_languages = ['en', 'kk', 'zh']

    for lang in target_languages:
        try:
            print(f"🔄 Переводим на {lang}...")

            # Переводим заголовок
            translated_title = translate_text(translations['ru']['title'], lang)
            translated_title = truncate_text(translated_title, 255)

            # Переводим основной текст
            translated_description = translate_text(body, lang)

            # Переводим подзаголовок (короткий)
            translated_subtitle = translate_text(short_subtitle, lang)
            translated_subtitle = truncate_text(translated_subtitle, 255)  # Ограничиваем до 255 символов

            translations[lang] = {
                'title': translated_title,
                'description': translated_description,
                'subtitle': translated_subtitle
            }

            print(f"✅ Перевод на {lang} завершен")
            print(f"   Заголовок: {translated_title}")
            print(f"   Подзаголовок: {translated_subtitle}")

        except Exception as e:
            print(f"❌ Ошибка перевода на {lang}: {e}")
            # В случае ошибки используем русский текст с ограничением длины
            translations[lang] = {
                'title': translations['ru']['title'],
                'description': translations['ru']['description'],
                'subtitle': translations['ru']['subtitle']
            }

    return translations


def extract_title_and_body(text: str):
    """Разделяет текст на заголовок и тело"""
    text = text.strip()

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
            # Только одна строка
            title = text
            body = ""

    # Ограничиваем длину
    title = truncate_text(title, 255)

    print(f"📄 Извлечен заголовок ({len(title)} символов): {title}")
    print(f"📄 Извлечен текст: {len(body)} символов")

    return title, body


def create_news_api(title: str, description: str, subtitle: str, image_uri: str, translations: dict) -> bool:
    """Создает новость через API"""
    global access_token

    if not access_token:
        if not login_to_api():
            return False

    news_url = f"{BASE_API_URL}/content/news"

    try:
        print("📤 Создаем новость через API...")

        # SEO настройки (ограничиваем длину)
        seo_keywords = {
            'ru': truncate_text("агро, сельское хозяйство, АПК, новости сельского хозяйства", 255),
            'en': truncate_text("agro, agriculture, agro-industrial complex, agricultural news", 255),
            'kk': truncate_text("агро, ауыл шаруашылығы, АӘК, ауыл шаруашылығы жаңалықтары", 255),
            'zh': truncate_text("农业, 农业综合企业, 农工综合体, 农业新闻", 255)
        }

        # Подготовка данных для API с ограничениями длины
        payload = {
            # Основные поля на русском
            "title": translations['ru']['title'],
            "description": translations['ru']['description'],
            "subtitle": translations['ru']['subtitle'],  # Максимум 255 символов
            "image_uri": image_uri,

            # Переводы на казахский
            "title_kk": translations['kk']['title'],
            "description_kk": translations['kk']['description'],
            "subtitle_kk": translations['kk']['subtitle'],

            # Переводы на английский
            "title_en": translations['en']['title'],
            "description_en": translations['en']['description'],
            "subtitle_en": translations['en']['subtitle'],

            # Переводы на китайский
            "title_zh": translations['zh']['title'],
            "description_zh": translations['zh']['description'],
            "subtitle_zh": translations['zh']['subtitle'],

            # SEO поля на русском
            "seo_title": truncate_text(translations['ru']['title'], 255),
            "seo_description": truncate_text(translations['ru']['subtitle'], 500),
            "seo_keywords": seo_keywords['ru'],
            "seo_image": image_uri,

            # SEO поля на казахском
            "seo_title_kk": truncate_text(translations['kk']['title'], 255),
            "seo_description_kk": truncate_text(translations['kk']['subtitle'], 500),
            "seo_keywords_kk": seo_keywords['kk'],

            # SEO поля на английском
            "seo_title_en": truncate_text(translations['en']['title'], 255),
            "seo_description_en": truncate_text(translations['en']['subtitle'], 500),
            "seo_keywords_en": seo_keywords['en'],

            # SEO поля на китайском
            "seo_title_zh": truncate_text(translations['zh']['title'], 255),
            "seo_description_zh": truncate_text(translations['zh']['subtitle'], 500),
            "seo_keywords_zh": seo_keywords['zh'],

            # Дополнительные поля
            "date_publication": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept-Language": "ru"
        }

        # Проверяем длину критических полей перед отправкой
        critical_fields = {
            'title': payload['title'],
            'subtitle': payload['subtitle'],
            'title_kk': payload['title_kk'],
            'subtitle_kk': payload['subtitle_kk'],
            'title_en': payload['title_en'],
            'subtitle_en': payload['subtitle_en'],
            'title_zh': payload['title_zh'],
            'subtitle_zh': payload['subtitle_zh']
        }

        for field_name, field_value in critical_fields.items():
            if len(field_value) > 255:
                print(f"⚠️ Поле {field_name} слишком длинное: {len(field_value)} символов")
                print(f"Значение: {field_value}")

        print(f"📊 Отправляем данные:")
        print(f"   Заголовок RU: '{payload['title']}' ({len(payload['title'])} симв.)")
        print(f"   Подзаголовок RU: '{payload['subtitle']}' ({len(payload['subtitle'])} симв.)")
        print(f"   Заголовок KK: '{payload['title_kk']}' ({len(payload['title_kk'])} симв.)")
        print(f"   Заголовок EN: '{payload['title_en']}' ({len(payload['title_en'])} симв.)")
        print(f"   Заголовок ZH: '{payload['title_zh']}' ({len(payload['title_zh'])} симв.)")
        print(f"   Image URI: '{payload['image_uri']}'")

        response = requests.post(news_url, json=payload, headers=headers, timeout=30)

        print(f"📡 Ответ сервера: {response.status_code}")

        if response.status_code == 201:
            result_data = response.json()
            print("✅ Новость успешно создана через API!")
            print(f"🎉 ID новости: {result_data.get('data', {}).get('id', 'N/A')}")
            return True
        else:
            print(f"❌ Ошибка создания новости: {response.status_code}")
            print(f"Ответ сервера: {response.text}")

            # Если токен просрочен, пробуем перелогиниться
            if response.status_code == 401:
                print("🔄 Токен устарел, пробуем переаутентифицироваться...")
                if login_to_api():
                    # Повторяем запрос с новым токеном
                    headers["Authorization"] = f"Bearer {access_token}"
                    response = requests.post(news_url, json=payload, headers=headers, timeout=30)

                    if response.status_code == 201:
                        print("✅ Новость успешно создана после переаутентификации!")
                        return True

            return False

    except Exception as e:
        print(f"❌ Ошибка при создании новости: {e}")
        return False


def post_news_to_site(news_text: str, image_path: str = None) -> bool:
    """Основная функция публикации новости через API"""

    # Шаг 1: Аутентификация
    if not login_to_api():
        print("❌ Не удалось аутентифицироваться в API")
        return False

    # Шаг 2: Извлечение заголовка и текста
    title, body = extract_title_and_body(news_text)

    # Шаг 3: Загрузка изображения
    image_uri = None
    if image_path and os.path.exists(image_path):
        image_uri = upload_image(image_path)
        if not image_uri:
            print("⚠️ Продолжаем без изображения")
    else:
        print("⚠️ Путь к изображению не указан или файл не существует")

    # Шаг 4: Перевод контента
    print("🔄 Начинаем перевод контента...")
    translations = translate_news_content(title, body)

    # Шаг 5: Создание новости
    subtitle = truncate_text(body, 200)  # Короткий подзаголовок
    success = create_news_api(title, body, subtitle, image_uri, translations)

    if success:
        print("🎉 Новость успешно опубликована на сайте через API!")
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
