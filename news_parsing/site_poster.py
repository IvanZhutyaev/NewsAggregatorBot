import requests
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
    """Разделяет текст на заголовок и тело"""
    # Ищем первое двойное перенос строки - разделитель между заголовком и телом
    parts = text.strip().split("\n\n", 1)

    if len(parts) == 2:
        # Есть и заголовок, и тело
        title = parts[0].strip()
        body = parts[1].strip()
    else:
        # Только заголовок или неправильный формат
        lines = text.strip().split("\n")
        if len(lines) > 1:
            # Берем первую строку как заголовок, остальное как тело
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
        else:
            # Только одна строка - используем как заголовок
            title = text.strip()
            body = ""

    # Очищаем заголовок от лишних символов и ограничиваем длину
    title = re.sub(r'[^\w\s\-–—.,!?;:()«»"]', '', title)
    title = title[:255]  # Ограничиваем длину для базы данных

    print(f"📄 Извлечен заголовок: {title}")
    print(f"📄 Извлечен текст: {body[:100]}..." if body else "📄 Текст отсутствует")

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
        token_tag = soup.find("meta", {"name": "csrf-token"})
        token = token_tag["content"] if token_tag else None
        if not token:
            print("⚠️ Не удалось найти CSRF токен на странице создания")
        return token
    except Exception as e:
        print(f"❌ Ошибка получения CSRF токена: {e}")
        return None


def post_news_to_site(news_text: str, image_path: str = None) -> bool:
    """Создание новости через Voyager admin"""
    if not login_to_site():
        return False

    csrf_token = get_csrf_token_for_create()
    if not csrf_token:
        print("❌ Не удалось получить CSRF токен для создания новости")
        return False

    create_url = f"{SITE_URL}/admin/news"
    title, body = extract_title_and_body(news_text)

    # Логируем данные для отладки
    print(f"📝 Данные для отправки:")
    print(f"Заголовок ({len(title)} симв.): {title}")
    print(f"Текст ({len(body)} симв.): {body[:100]}..." if body else "Текст отсутствует")
    print(f"CSRF токен: {csrf_token[:20]}...")

    # Подготавливаем данные - только необходимые поля
    data = {
        "_token": csrf_token,
        "title_ru": title,
        "subtitle_ru": title[:100],  # краткий заголовок
        "description_ru": body,
        "seo_title_ru": title[:60],
        "seo_description_ru": body[:160] if body else title[:160],
        "seo_keywords_ru": ", ".join(title.split()[:5]),
        "seo_url": "",
        # Возможно нужны дополнительные поля:
        # "category_id": "1",
        # "status": "PUBLISHED",
        # "author_id": "1",
    }

    # Сначала попробуем без изображения
    files = {}
    # if image_path:
    #     try:
    #         files["image"] = open(image_path, "rb")
    #         print(f"🖼️ Изображение: {image_path}")
    #     except Exception as e:
    #         print(f"⚠️ Не удалось открыть изображение: {e}")

    try:
        print(f"🌐 Отправляем запрос на: {create_url}")
        response = session.post(create_url, data=data, files=files, timeout=20)

        if files:
            files["image"].close()

        print(f"📡 Ответ сервера: {response.status_code}")

        # Детальный анализ ответа
        if response.status_code == 500:
            print("❌ Ошибка 500 - внутренняя ошибка сервера")
            print("🔍 Тело ответа:")
            print(response.text[:1000])  # Больше символов для анализа
            return False

        if response.status_code in (200, 302):
            if "voyager/news" in response.text or response.status_code == 302:
                print("🌐 Новость успешно опубликована на сайте!")
                return True
            else:
                print("⚠️ Ответ не подтверждает успешное добавление.")
                # Проверяем на наличие сообщений об успехе
                if "успешно" in response.text.lower() or "success" in response.text.lower():
                    print("✅ Похоже, новость добавлена успешно (найдены ключевые слова)")
                    return True
                return False
        else:
            print(f"❌ Ошибка публикации: {response.status_code}")
            print(f"Текст ответа: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Ошибка при отправке новости: {e}")
        return False


def analyze_create_form():
    """Анализирует форму создания новости для отладки"""
    if not login_to_site():
        return

    create_url = f"{SITE_URL}/admin/news/create"
    try:
        resp = session.get(create_url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        print("🔍 Анализ формы создания новости:")

        # Ищем все поля формы
        form = soup.find('form')
        if form:
            inputs = form.find_all('input')
            textareas = form.find_all('textarea')
            selects = form.find_all('select')

            print(f"📋 Найдено полей:")
            print(f"Inputs: {len(inputs)}")
            for inp in inputs:
                name = inp.get('name', 'без имени')
                type_ = inp.get('type', 'без типа')
                print(f"  - {name} (type: {type_})")

            print(f"Textareas: {len(textareas)}")
            for ta in textareas:
                name = ta.get('name', 'без имени')
                print(f"  - {name}")

            print(f"Selects: {len(selects)}")
            for sel in selects:
                name = sel.get('name', 'без имени')
                print(f"  - {name}")

        # Ищем CSRF токен
        token_tag = soup.find("meta", {"name": "csrf-token"})
        if token_tag:
            print(f"✅ CSRF токен найден: {token_tag['content'][:20]}...")
        else:
            print("❌ CSRF токен не найден")

    except Exception as e:
        print(f"❌ Ошибка анализа формы: {e}")


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