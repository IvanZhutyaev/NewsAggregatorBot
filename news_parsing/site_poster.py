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
    title = title[:255]  # Ограничиваем длину

    print(f"📄 Извлечен заголовок: {title}")
    print(f"📄 Извлечен текст: {len(body)} символов")

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

        # Ищем форму создания новости
        form = soup.find('form')
        if not form:
            print("❌ Форма не найдена на странице")
            return None

        print("✅ Форма создания новости найдена")

        # Ищем CSRF токен в форме
        token_tag = form.find("input", {"name": "_token"})
        if token_tag:
            csrf_token = token_tag["value"]
            print(f"✅ CSRF токен найден: {csrf_token[:20]}...")
            return csrf_token

        print("❌ CSRF токен не найден в форме")
        return None

    except Exception as e:
        print(f"❌ Ошибка получения CSRF токена: {e}")
        return None


def post_news_to_site(news_text: str, image_path: str = None) -> bool:
    """Создание новости через правильную форму"""
    if not login_to_site():
        return False

    csrf_token = get_csrf_token_for_create()
    if not csrf_token:
        print("❌ Не удалось получить CSRF токен для создания новости")
        return False

    # ПРАВИЛЬНЫЙ URL для отправки формы
    create_url = f"{SITE_URL}/admin/news"  # Это endpoint для сохранения

    title, body = extract_title_and_body(news_text)

    print(f"📝 Отправляем данные на: {create_url}")
    print(f"Заголовок: {title}")
    print(f"Текст: {body[:100]}...")

    # Правильные данные для Voyager формы
    data = {
        "_token": csrf_token,
        # Основные поля
        "title": title,
        "subtitle": title[:100],
        "description": body,
        # SEO поля
        "seo_title": title[:60],
        "seo_description": body[:160] if body else title[:160],
        "seo_keywords": ", ".join(title.split()[:5]),
        "seo_slug": "",
        # Обязательные скрытые поля
        "redirect_to": "",
        "model_name": "App\\Models\\News",
        "model_id": "",
        "type_slug": "news",
    }

    files = {}
    if image_path:
        try:
            files["image"] = open(image_path, "rb")
            print(f"🖼️ Изображение: {image_path}")
        except Exception as e:
            print(f"⚠️ Не удалось открыть изображение: {e}")

    try:
        response = session.post(create_url, data=data, files=files, timeout=20)

        if files:
            files["image"].close()

        print(f"📡 Ответ сервера: {response.status_code}")

        # Детальный анализ ответа
        if response.status_code == 500:
            print("❌ Ошибка 500 - внутренняя ошибка сервера")
            print("🔍 Тело ответа:")
            error_text = response.text
            print(error_text[:1000])
            return False

        if response.status_code in (200, 302):
            # Проверяем успешность по редиректу или содержимому
            if response.status_code == 302:
                print("✅ Новость успешно создана (редирект)!")
                return True

            if "успех" in response.text.lower() or "success" in response.text.lower():
                print("✅ Новость успешно создана!")
                return True

            # Проверяем, нет ли ошибок в ответе
            soup = BeautifulSoup(response.text, "html.parser")
            errors = soup.find_all(class_=['error', 'alert-danger'])
            if errors:
                for error in errors:
                    print(f"❌ Ошибка: {error.get_text(strip=True)}")
                return False

            print("⚠️ Статус 200, но нет явного подтверждения успеха")
            return True

        else:
            print(f"❌ Ошибка публикации: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Ошибка при отправке новости: {e}")
        return False


def post_news_to_site_alternative(news_text: str, image_path: str = None) -> bool:
    """Альтернативный метод - минимальный набор полей"""
    if not login_to_site():
        return False

    csrf_token = get_csrf_token_for_create()
    if not csrf_token:
        return False

    create_url = f"{SITE_URL}/admin/news"
    title, body = extract_title_and_body(news_text)

    print("🔄 Пробуем альтернативный метод (минимальные поля)...")

    # Абсолютно минимальный набор полей
    data = {
        "_token": csrf_token,
        "title": title,
        "description": body,
        "i18n_selector": "ru",  # Важно: указываем язык
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
            return False

    except Exception as e:
        print(f"❌ Ошибка альтернативного метода: {e}")
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


def test_form_manually():
    """Ручное тестирование формы"""
    if not login_to_site():
        return

    create_url = f"{SITE_URL}/admin/news/create"
    try:
        # Получаем страницу создания
        resp = session.get(create_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        print("🧪 Ручное тестирование формы:")
        print("=" * 50)

        # Ищем форму
        form = soup.find('form')
        if form:
            action = form.get('action', '')
            method = form.get('method', 'post')
            print(f"Форма: action='{action}', method='{method}'")

            # Показываем все поля формы
            inputs = form.find_all('input')
            print(f"Всего input полей: {len(inputs)}")

            # Группируем по типам
            text_inputs = [inp for inp in inputs if inp.get('type') == 'text']
            hidden_inputs = [inp for inp in inputs if inp.get('type') == 'hidden']
            file_inputs = [inp for inp in inputs if inp.get('type') == 'file']

            print(f"Text поля: {len(text_inputs)}")
            for inp in text_inputs:
                name = inp.get('name')
                placeholder = inp.get('placeholder', '')
                print(f"  - {name}: '{placeholder}'")

            print(f"Hidden поля: {len(hidden_inputs)}")
            for inp in hidden_inputs[:5]:  # Показываем первые 5
                name = inp.get('name')
                value = inp.get('value', '')[:50]
                print(f"  - {name}: '{value}'")

            print(f"File поля: {len(file_inputs)}")
            for inp in file_inputs:
                name = inp.get('name')
                print(f"  - {name}")

        # Проверяем textarea
        textareas = soup.find_all('textarea')
        print(f"Textarea поля: {len(textareas)}")
        for ta in textareas:
            name = ta.get('name')
            placeholder = ta.get('placeholder', '')
            print(f"  - {name}: '{placeholder}'")

    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")


def debug_form_submission():
    """Отладочная функция для тестирования отправки формы"""
    if not login_to_site():
        return

    create_url = f"{SITE_URL}/admin/news/create"
    try:
        print("🐛 Отладочная информация о форме:")
        print("=" * 50)

        # Получаем страницу
        resp = session.get(create_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Находим форму
        form = soup.find('form')
        if form:
            action = form.get('action', '')
            method = form.get('method', '')
            print(f"Форма action: {action}")
            print(f"Форма method: {method}")

            # Все поля формы
            inputs = form.find_all('input')
            print(f"Всего input полей: {len(inputs)}")

            for inp in inputs:
                name = inp.get('name', '')
                input_type = inp.get('type', '')
                value = inp.get('value', '')[:50]
                if name:  # Показываем только поля с именем
                    print(f"  {name} (type: {input_type}) = '{value}'")

            # Textareas
            textareas = form.find_all('textarea')
            print(f"Textarea полей: {len(textareas)}")
            for ta in textareas:
                name = ta.get('name', '')
                if name:
                    print(f"  {name}")

        else:
            print("❌ Форма не найдена!")

    except Exception as e:
        print(f"❌ Ошибка отладки: {e}")