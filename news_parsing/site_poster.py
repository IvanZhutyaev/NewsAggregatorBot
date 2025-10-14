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

    # Пробуем разные варианты полей
    data_variants = [
        # Вариант 1: Только базовые поля
        {
            "_token": csrf_token,
            "title": title,
            "body": body,
        },
        # Вариант 2: С русскими полями
        {
            "_token": csrf_token,
            "title_ru": title,
            "body_ru": body,
        },
        # Вариант 3: Полный набор полей
        {
            "_token": csrf_token,
            "title": title,
            "title_ru": title,
            "title_en": title,
            "title_kk": title,
            "body": body,
            "body_ru": body,
            "body_en": body,
            "body_kk": body,
            "excerpt": body[:200] if body else title[:200],
            "slug": "",
            "status": "PUBLISHED",
            "category_id": "1",
            "author_id": "1",
        },
        # Вариант 4: Альтернативные названия полей
        {
            "_token": csrf_token,
            "name": title,
            "name_ru": title,
            "content": body,
            "content_ru": body,
            "description": body,
            "description_ru": body,
        }
    ]

    files = {}
    if image_path:
        try:
            files["image"] = open(image_path, "rb")
            print(f"🖼️ Изображение: {image_path}")
        except Exception as e:
            print(f"⚠️ Не удалось открыть изображение: {e}")

    # Пробуем все варианты данных
    for i, data in enumerate(data_variants, 1):
        print(f"🔧 Пробуем вариант {i}/4...")

        try:
            print(f"🌐 Отправляем запрос на: {create_url}")
            response = session.post(create_url, data=data, files=files, timeout=20)

            print(f"📡 Ответ сервера: {response.status_code}")

            if response.status_code == 200:
                # Проверяем успешность по содержимому ответа
                if any(keyword in response.text.lower() for keyword in ['success', 'успех', 'создан', 'добавлен']):
                    print(f"✅ Новость успешно опубликована (вариант {i})!")
                    if files:
                        files["image"].close()
                    return True
                else:
                    print(f"⚠️ Ответ 200, но нет подтверждения успеха (вариант {i})")
            elif response.status_code == 302:
                print(f"✅ Новость опубликована (редирект) (вариант {i})!")
                if files:
                    files["image"].close()
                return True
            elif response.status_code == 500:
                print(f"❌ Ошибка 500 с вариантом {i}")
                # Продолжаем пробовать следующий вариант
                continue
            else:
                print(f"❌ Ошибка {response.status_code} с вариантом {i}")

        except Exception as e:
            print(f"❌ Ошибка при отправке (вариант {i}): {e}")
            continue

    if files:
        files["image"].close()

    print("❌ Все варианты данных не сработали")
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


def analyze_real_form_fields():
    """Анализирует реальные поля формы через JavaScript или HTML"""
    if not login_to_site():
        return

    create_url = f"{SITE_URL}/admin/news/create"
    try:
        resp = session.get(create_url, timeout=10)

        print("🔍 Детальный анализ формы:")
        print("=" * 50)

        # Ищем все возможные поля ввода
        soup = BeautifulSoup(resp.text, "html.parser")

        # Все input элементы
        print("📋 INPUT поля:")
        inputs = soup.find_all('input')
        for inp in inputs:
            name = inp.get('name', 'без имени')
            input_type = inp.get('type', 'text')
            value = inp.get('value', '')
            placeholder = inp.get('placeholder', '')
            print(f"  - name: '{name}', type: '{input_type}', value: '{value}', placeholder: '{placeholder}'")

        # Все textarea элементы
        print("\n📋 TEXTAREA поля:")
        textareas = soup.find_all('textarea')
        for ta in textareas:
            name = ta.get('name', 'без имени')
            placeholder = ta.get('placeholder', '')
            print(f"  - name: '{name}', placeholder: '{placeholder}'")

        # Все select элементы
        print("\n📋 SELECT поля:")
        selects = soup.find_all('select')
        for sel in selects:
            name = sel.get('name', 'без имени')
            options = sel.find_all('option')
            print(f"  - name: '{name}', options: {len(options)}")
            for opt in options[:3]:  # Показываем первые 3 опции
                print(f"    * {opt.get('value', '')} - {opt.text}")

        # Ищем JavaScript переменные с настройками
        print("\n🔍 JavaScript данные:")
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                js_content = script.string
                # Ищем упоминания полей в JS
                if any(field in js_content for field in ['title', 'body', 'content', 'description']):
                    lines = js_content.split('\n')
                    for line in lines[:10]:  # Первые 10 строк
                        if any(field in line for field in ['title', 'body', 'content', 'description']):
                            print(f"  JS: {line.strip()}")

    except Exception as e:
        print(f"❌ Ошибка анализа формы: {e}")