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
    title = title[:255]  # Ограничиваем длину

    # Очищаем тело текста
    body = re.sub(r'\s+', ' ', body)  # Заменяем множественные пробелы на один

    print(f"📄 Извлечен заголовок: {title}")
    print(f"📄 Извлечен текст: {len(body)} символов")
    print(f"📄 Подзаголовок (первые 100 символов): {body[:100]}...")

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
    """Исправленная версия с подзаголовком и изображениями"""
    if not login_to_site():
        return False

    csrf_token = get_csrf_token_for_create()
    if not csrf_token:
        return False

    create_url = f"{SITE_URL}/admin/news"
    title, body = extract_title_and_body(news_text)

    print("🔄 Используем правильный формат для ВСЕХ translatable полей Voyager...")
    print(f"📝 Отправляем данные на: {create_url}")

    # Создаем подзаголовок из первых 100 символов текста
    subtitle = body[:100] + "..." if len(body) > 100 else body

    # Генерируем SEO поля на основе заголовка и текста
    seo_title = title[:60]  # Ограничиваем для SEO
    seo_description = body[:160] if body else title[:160]  # Ограничиваем для SEO
    seo_keywords = "агро, сельское хозяйство, новости, АПК"  # Базовые ключевые слова

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
        "subtitle": subtitle,  # Добавляем подзаголовок
        "description": body,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "seo_keywords": seo_keywords,

        # Дополнительные поля, которые могут быть нужны
        "status": "PUBLISHED",
        "category_id": "",  # Можно указать ID категории если нужно
        "author_id": "",  # Можно указать ID автора если нужно
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
            # Основное изображение
            files["image"] = open(image_path, "rb")
            print(f"🖼️ Основное изображение: {image_path}")

            # SEO изображение (может быть тем же самым)
            files["seo_image"] = open(image_path, "rb")
            print(f"🔍 SEO изображение: {image_path}")

        except Exception as e:
            print(f"⚠️ Не удалось открыть изображение: {e}")
    else:
        print("⚠️ Изображение не найдено или путь не указан")

    try:
        response = session.post(create_url, data=data, files=files, timeout=30)

        # Закрываем файлы
        for file_obj in files.values():
            file_obj.close()

        print(f"📡 Ответ сервера: {response.status_code}")

        if response.status_code == 500:
            print("❌ Ошибка 500 - внутренняя ошибка сервера")

            # Сохраняем детальную информацию об ошибке
            error_content = response.text
            with open("error_detailed.html", "w", encoding="utf-8") as f:
                f.write(error_content)

            # Анализируем ошибку
            if "Invalid Translatable field" in error_content:
                print("🔍 Проблема с translatable полями!")

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
            if 'i18n' in name:  # Показываем только translatable поля
                print(f"  - name: '{name}', type: '{input_type}', value: '{value}', placeholder: '{placeholder}'")

        # Все textarea элементы
        print("\n📋 TEXTAREA поля:")
        textareas = soup.find_all('textarea')
        for ta in textareas:
            name = ta.get('name', 'без имени')
            placeholder = ta.get('placeholder', '')
            if 'i18n' in name:  # Показываем только translatable поля
                print(f"  - name: '{name}', placeholder: '{placeholder}'")

        # Все select элементы
        print("\n📋 SELECT поля:")
        selects = soup.find_all('select')
        for sel in selects:
            name = sel.get('name', 'без имени')
            if 'i18n' in name:  # Показываем только translatable поля
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
                # Ищем упоминания translatable полей в JS
                if any(field in js_content for field in ['i18n', 'translatable']):
                    lines = js_content.split('\n')
                    for line in lines[:20]:  # Первые 20 строк
                        if any(field in line for field in ['i18n', 'translatable']):
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


def find_correct_form_endpoint():
    """Поиск правильного endpoint для формы"""
    if not login_to_site():
        return None

    create_url = f"{SITE_URL}/admin/news/create"
    try:
        resp = session.get(create_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Ищем JavaScript который может содержать endpoint
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                content = script.string
                if 'action' in content and 'news' in content:
                    print("🔍 Найден возможный endpoint в JS:")
                    lines = content.split('\n')
                    for line in lines:
                        if 'action' in line and 'news' in line:
                            print(f"  JS: {line.strip()}")

        # Проверяем различные возможные endpoints
        endpoints = [
            f"{SITE_URL}/admin/news",
            f"{SITE_URL}/admin/news/store",
            f"{SITE_URL}/admin/news/save",
            f"{SITE_URL}/admin/news/create"
        ]

        for endpoint in endpoints:
            print(f"🔍 Проверяем endpoint: {endpoint}")
            # Можно добавить тестовые запросы здесь

        return f"{SITE_URL}/admin/news"  # По умолчанию

    except Exception as e:
        print(f"❌ Ошибка поиска endpoint: {e}")
        return None


def debug_current_form():
    """Отладочная функция для анализа текущей структуры формы"""
    if not login_to_site():
        return

    create_url = f"{SITE_URL}/admin/news/create"
    try:
        resp = session.get(create_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        print("🔍 Текущая структура формы:")
        form = soup.find('form')
        if form:
            # Найти все поля с именем содержащим 'i18n'
            i18n_fields = form.find_all(attrs={"name": lambda x: x and 'i18n' in x})
            print(f"Найдено i18n полей: {len(i18n_fields)}")
            for field in i18n_fields:
                print(f"  - {field.get('name')}")

    except Exception as e:
        print(f"❌ Ошибка отладки: {e}")


def test_all_translatable_fields():
    """Тестирует отправку всех возможных translatable полей"""
    if not login_to_site():
        return False

    csrf_token = get_csrf_token_for_create()
    if not csrf_token:
        return False

    create_url = f"{SITE_URL}/admin/news"
    title = "Тестовая новость"
    body = "Тестовое содержание новости"

    print("🧪 Тестируем все возможные translatable поля...")

    # Пробуем разные комбинации translatable полей
    test_cases = [
        {
            "name": "Только основные поля",
            "data": {
                "_token": csrf_token,
                "i18n_selector": "ru",
                "title_i18n": json.dumps({"ru": title}),
                "description_i18n": json.dumps({"ru": body}),
            }
        },
        {
            "name": "С subtitle",
            "data": {
                "_token": csrf_token,
                "i18n_selector": "ru",
                "title_i18n": json.dumps({"ru": title}),
                "subtitle_i18n": json.dumps({"ru": "Тестовый подзаголовок"}),
                "description_i18n": json.dumps({"ru": body}),
            }
        },
        {
            "name": "Только обычные поля",
            "data": {
                "_token": csrf_token,
                "title": title,
                "description": body,
            }
        }
    ]

    for i, test_case in enumerate(test_cases):
        print(f"\n🔍 Тест {i + 1}: {test_case['name']}")
        try:
            response = session.post(create_url, data=test_case['data'], timeout=10)
            print(f"📡 Ответ: {response.status_code}")

            if response.status_code == 500:
                print("❌ Ошибка 500")
            elif response.status_code in (200, 302):
                print("✅ Успех!")
                return True

        except Exception as e:
            print(f"❌ Ошибка: {e}")

    return False


def debug_form_submission_detailed():
    """Детальная отладка отправки формы"""
    if not login_to_site():
        return

    create_url = f"{SITE_URL}/admin/news/create"
    try:
        resp = session.get(create_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        print("🔍 Детальная отладка формы:")
        print("=" * 60)

        # Находим все скрытые поля с i18n
        hidden_i18n_fields = soup.find_all('input', {'type': 'hidden', 'name': lambda x: x and 'i18n' in x})
        print(f"📋 Найдено скрытых i18n полей: {len(hidden_i18n_fields)}")

        for field in hidden_i18n_fields:
            name = field.get('name')
            value = field.get('value', '')[:100]  # Показываем первые 100 символов
            print(f"  - {name}: {value}")

        # Проверяем структуру JSON в значениях по умолчанию
        for field in hidden_i18n_fields:
            name = field.get('name')
            value = field.get('value', '')
            try:
                parsed = json.loads(value)
                print(f"  ✅ {name}: валидный JSON, ключи: {list(parsed.keys())}")
            except:
                print(f"  ❌ {name}: невалидный JSON")

    except Exception as e:
        print(f"❌ Ошибка отладки: {e}")


def analyze_image_upload():
    """Анализирует поля для загрузки изображений"""
    if not login_to_site():
        return

    create_url = f"{SITE_URL}/admin/news/create"
    try:
        resp = session.get(create_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        print("🔍 Анализ полей для изображений:")
        print("=" * 50)

        # Ищем все поля типа file
        file_inputs = soup.find_all('input', {'type': 'file'})
        print(f"📋 Найдено полей для загрузки файлов: {len(file_inputs)}")

        for file_input in file_inputs:
            name = file_input.get('name', 'без имени')
            accept = file_input.get('accept', '')
            print(f"  - Поле: '{name}', принимает: '{accept}'")

        # Ищем связанные с изображениями поля
        image_related = soup.find_all(['input', 'textarea', 'select'],
                                      attrs={'name': lambda x: x and 'image' in x.lower()})
        print(f"📋 Найдено полей связанных с изображениями: {len(image_related)}")

        for field in image_related:
            name = field.get('name', 'без имени')
            field_type = field.name
            print(f"  - {name} (тип: {field_type})")

    except Exception as e:
        print(f"❌ Ошибка анализа полей изображений: {e}")