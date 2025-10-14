import os
from datetime import datetime

import requests
import json
from bs4 import BeautifulSoup
from config import SITE_URL, SITE_LOGIN, SITE_PASSWORD
import re
session = requests.Session()


def login_to_site() -> bool:
    """Авторизация в админ-панели Voyager"""
    login_url = f"{SITE_URL}/admin/login"
    try:
        print("🔑 Входим в админ-панель...")

        # Получаем CSRF токен со страницы логина
        login_page = session.get(login_url, timeout=10)
        soup = BeautifulSoup(login_page.text, "html.parser")
        token_tag = soup.find("input", {"name": "_token"})
        csrf_token = token_tag["value"] if token_tag else None

        if not csrf_token:
            print("⚠️ Не найден CSRF токен на странице логина")
            return False

        data = {
            "email": SITE_LOGIN,
            "password": SITE_PASSWORD,
            "_token": csrf_token
        }

        resp = session.post(login_url, data=data, timeout=10)
        if "voyager-dashboard" in resp.text or "logout" in resp.text:
            print("✅ Авторизация прошла успешно")
            return True
        else:
            print("⚠️ Авторизация не удалась. Проверь логин/пароль.")
            return False
    except Exception as e:
        print(f"❌ Ошибка авторизации: {e}")
        return False


def extract_title_and_body(text: str):
    """Разделяет текст на заголовок и тело с улучшенной логикой"""
    # Убираем лишние пробелы
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

    # Очищаем и ограничиваем заголовок
    title = re.sub(r'\s+', ' ', title)  # Заменяем множественные пробелы на один
    title = title[:80]  # Оптимальная длина для заголовка

    # Очищаем тело текста
    body = re.sub(r'\s+', ' ', body)  # Заменяем множественные пробелы на один

    print(f"📄 Извлечен заголовок ({len(title)} символов): {title}")
    print(f"📄 Извлечен текст: {len(body)} символов")
    print(f"📄 Подзаголовок ({len(body[:120])} символов): {body[:120]}...")

    return title, body

def get_csrf_token_for_create() -> str:
    """Получаем CSRF токен со страницы создания новости"""
    create_url = f"{SITE_URL}/admin/news/create"
    try:
        resp = session.get(create_url, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ Ошибка при получении страницы создания: {resp.status_code}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Ищем ВСЕ формы на странице
        forms = soup.find_all('form')
        print(f"🔍 Найдено форм на странице: {len(forms)}")

        for i, form in enumerate(forms):
            action = form.get('action', '')
            method = form.get('method', '')
            print(f"  Форма {i + 1}: action='{action}', method='{method}'")

        # Ищем форму с правильным action (обычно action='' или action='/admin/news')
        target_form = None
        for form in forms:
            action = form.get('action', '')
            # Ищем форму, которая не ведет на logout и не имеет подозрительного action
            if 'logout' not in action and not action.startswith('/admin/logout'):
                target_form = form
                break

        if not target_form and forms:
            # Если не нашли подходящую, берем первую форму
            target_form = forms[0]

        if not target_form:
            print("❌ Форма не найдена на странице")
            return None

        print("✅ Форма создания новости найдена")

        # Ищем CSRF токен в форме
        token_tag = target_form.find("input", {"name": "_token"})
        if token_tag:
            csrf_token = token_tag["value"]
            print(f"✅ CSRF токен найден: {csrf_token[:20]}...")
            return csrf_token

        print("❌ CSRF токен не найден в форме")
        return None

    except Exception as e:
        print(f"❌ Ошибка получения CSRF токена: {e}")
        return None


def post_news_to_site_simple(news_text: str, image_path: str = None) -> bool:
    """Исправленная версия с правильной загрузкой изображений"""
    if not login_to_site():
        return False

    csrf_token = get_csrf_token_for_create()
    if not csrf_token:
        return False

    create_url = f"{SITE_URL}/admin/news"
    title, body = extract_title_and_body(news_text)

    print("🔄 Используем правильный формат для ВСЕХ translatable полей Voyager...")
    print(f"📝 Отправляем данные на: {create_url}")

    # ОПТИМАЛЬНЫЕ ДЛИНЫ ДЛЯ ПОЛЕЙ VOYAGER:
    title = title[:80]
    subtitle = body[:120].strip()
    if len(body) > 120:
        subtitle += "..."
    seo_title = title[:55]
    seo_description = body[:155].strip()
    if len(body) > 155:
        seo_description += "..."
    seo_keywords = "агро, сельское хозяйство, АПК, новости сельского хозяйства"

    print(f"📊 Оптимизированные длины полей:")
    print(f"  - Заголовок: {len(title)} символов")
    print(f"  - Подзаголовок: {len(subtitle)} символов")
    print(f"  - SEO заголовок: {len(seo_title)} символов")
    print(f"  - SEO описание: {len(seo_description)} символов")

    # ПРАВИЛЬНЫЙ формат для ВСЕХ translatable полей в Voyager
    data = {
        "_token": csrf_token,
        "i18n_selector": "ru",

        # ВСЕ translatable поля в правильном формате для Voyager
        "title_i18n": json.dumps({"ru": title, "kk": "", "en": "", "zh": ""}),
        "subtitle_i18n": json.dumps({"ru": subtitle, "kk": "", "en": "", "zh": ""}),
        "description_i18n": json.dumps({"ru": body, "kk": "", "en": "", "zh": ""}),
        "seo_title_i18n": json.dumps({"ru": seo_title, "kk": "", "en": "", "zh": ""}),
        "seo_description_i18n": json.dumps({"ru": seo_description, "kk": "", "en": "", "zh": ""}),
        "seo_keywords_i18n": json.dumps({"ru": seo_keywords, "kk": "", "en": "", "zh": ""}),

        # Также отправляем обычные поля
        "title": title,
        "subtitle": subtitle,
        "description": body,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "seo_keywords": seo_keywords,

        # Дополнительные поля
        "status": "PUBLISHED",
        "published_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        # Системные поля
        "redirect_to": "",
        "model_name": "App\\Models\\News",
        "model_id": "",
        "type_slug": "news",
    }

    files = {}
    if image_path and os.path.exists(image_path):
        try:
            print("🖼️ Загружаем изображения с правильными именами:")

            # Пробуем разные варианты имен файлов
            image_filename = os.path.basename(image_path)

            # Вариант 1: Основное изображение
            files["image"] = (image_filename, open(image_path, "rb"), 'image/jpeg')
            print(f"  ✅ image как '{image_filename}'")

            # Вариант 2: SEO изображение
            files["seo_image"] = (f"seo_{image_filename}", open(image_path, "rb"), 'image/jpeg')
            print(f"  ✅ seo_image как 'seo_{image_filename}'")

            # Вариант 3: image_uri (может быть нужно)
            files["image_uri"] = (f"uri_{image_filename}", open(image_path, "rb"), 'image/jpeg')
            print(f"  ✅ image_uri как 'uri_{image_filename}'")

        except Exception as e:
            print(f"⚠️ Не удалось открыть изображение: {e}")
    else:
        print("⚠️ Изображение не найдено или путь не указан")

    try:
        print("📤 Отправляем запрос с файлами...")
        response = session.post(create_url, data=data, files=files, timeout=30)

        # Закрываем файлы
        for file_obj in files.values():
            if hasattr(file_obj[1], 'close'):
                file_obj[1].close()

        print(f"📡 Ответ сервера: {response.status_code}")

        if response.status_code == 500:
            print("❌ Ошибка 500 - внутренняя ошибка сервера")

            # Сохраняем ошибку для анализа
            error_content = response.text
            with open("error_image_upload.html", "w", encoding="utf-8") as f:
                f.write(error_content)
            print("🔍 Детали ошибки сохранены в error_image_upload.html")

            return False

        if response.status_code in (200, 302):
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if 'admin/news' in location or 'success' in location.lower():
                    print("✅ Новость успешно создана (редирект на список новостей)!")
                    return True
                else:
                    print(f"⚠️ Редирект на: {location}")
                    return True

            # Проверяем успешность по содержимому
            success_indicators = ['успех', 'success', 'создан', 'created']
            if any(indicator in response.text.lower() for indicator in success_indicators):
                print("✅ Новость успешно создана!")
                return True

            # Если нет явных ошибок, считаем успешным
            error_indicators = ['error', 'ошибка', 'exception', 'invalid']
            if not any(indicator in response.text.lower() for indicator in error_indicators):
                print("✅ Новость создана (нет ошибок в ответе)!")
                return True

            print("⚠️ Возможная ошибка в ответе")
            return False
        else:
            print(f"❌ Ошибка публикации: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Ошибка при отправке новости: {e}")
        return False

def post_news_to_site(news_text: str, image_path: str = None) -> bool:
    """Основная функция публикации новости"""
    return post_news_to_site_simple(news_text, image_path)


def post_news_to_site_alternative(news_text: str, image_path: str = None) -> bool:
    """Альтернативный метод - отправка через имитацию браузера"""
    if not login_to_site():
        return False

    csrf_token = get_csrf_token_for_create()
    if not csrf_token:
        return False

    create_url = f"{SITE_URL}/admin/news"
    title, body = extract_title_and_body(news_text)

    print("🔄 Альтернативный метод - минимальный набор translatable полей...")

    # Минимальный набор translatable полей
    data = {
        "_token": csrf_token,
        "i18n_selector": "ru",

        # Только обязательные translatable поля
        "title_i18n": json.dumps({"ru": title, "kk": "", "en": "", "zh": ""}),
        "description_i18n": json.dumps({"ru": body, "kk": "", "en": "", "zh": ""}),

        # Обычные поля
        "title": title,
        "description": body,
    }

    files = {}
    if image_path:
        try:
            files["image"] = open(image_path, "rb")
        except Exception as e:
            print(f"⚠️ Не удалось открыть изображение: {e}")

    try:
        response = session.post(create_url, data=data, files=files, timeout=20)

        if files:
            files["image"].close()

        print(f"📡 Ответ альтернативного метода: {response.status_code}")

        if response.status_code in (200, 302):
            print("✅ Новость опубликована альтернативным методом!")
            return True
        else:
            print(f"❌ Ошибка альтернативного метода: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Ошибка альтернативного метода: {e}")
        return False



def check_required_fields():
    """Проверяет обязательные поля формы"""
    if not login_to_site():
        return

    create_url = f"{SITE_URL}/admin/news/create"
    try:
        resp = session.get(create_url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        print("🔍 Поиск обязательных полей:")

        # Ищем поля с атрибутом required
        required_fields = []
        all_inputs = soup.find_all('input')
        all_textareas = soup.find_all('textarea')
        all_selects = soup.find_all('select')

        for field in all_inputs + all_textareas + all_selects:
            if field.get('required'):
                name = field.get('name', 'без имени')
                required_fields.append(name)
                field_type = field.name
                print(f"⚠️ Обязательное поле: {name} (тип: {field_type})")

        if not required_fields:
            print("✅ Обязательных полей не найдено")

        return required_fields

    except Exception as e:
        print(f"❌ Ошибка проверки полей: {e}")
        return []