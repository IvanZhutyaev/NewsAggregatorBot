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

    # Правильные данные на основе анализа формы
    data = {
        "_token": csrf_token,
        # Основные поля
        "title": title,
        "subtitle": title[:100],  # краткий заголовок
        "description": body,
        # SEO поля
        "seo_title": title[:60],
        "seo_description": body[:160] if body else title[:160],
        "seo_keywords": ", ".join(title.split()[:5]),
        "seo_slug": "",
        # Скрытые поля i18n (мультиязычность)
        "title_i18n": '{"ru":"' + title + '","kk":"' + title + '","en":"' + title + '","zh":"' + title + '"}',
        "subtitle_i18n": '{"ru":"' + title[:100] + '","kk":"' + title[:100] + '","en":"' + title[
                                                                                           :100] + '","zh":"' + title[
                                                                                                                :100] + '"}',
        "description_i18n": '{"ru":"' + body + '","kk":"' + body + '","en":"' + body + '","zh":"' + body + '"}',
        "seo_title_i18n": '{"ru":"' + title[:60] + '","kk":"' + title[:60] + '","en":"' + title[
                                                                                          :60] + '","zh":"' + title[
                                                                                                              :60] + '"}',
        "seo_description_i18n": '{"ru":"' + (body[:160] if body else title[:160]) + '","kk":"' + (
            body[:160] if body else title[:160]) + '","en":"' + (body[:160] if body else title[:160]) + '","zh":"' + (
                                    body[:160] if body else title[:160]) + '"}',
        "seo_keywords_i18n": '{"ru":"' + ", ".join(title.split()[:5]) + '","kk":"' + ", ".join(
            title.split()[:5]) + '","en":"' + ", ".join(title.split()[:5]) + '","zh":"' + ", ".join(
            title.split()[:5]) + '"}',
        # Дополнительные поля
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
        print(f"🌐 Отправляем запрос на: {create_url}")
        response = session.post(create_url, data=data, files=files, timeout=20)

        if files:
            files["image"].close()

        print(f"📡 Ответ сервера: {response.status_code}")

        # Детальный анализ ответа
        if response.status_code == 500:
            print("❌ Ошибка 500 - внутренняя ошибка сервера")
            print("🔍 Тело ответа:")
            error_text = response.text
            print(error_text[:1500])  # Больше символов для анализа

            # Ищем конкретную ошибку в тексте
            if "title_i18n" in error_text:
                print("⚠️ Проблема с полем title_i18n")
            if "description_i18n" in error_text:
                print("⚠️ Проблема с полем description_i18n")

            return False

        if response.status_code in (200, 302):
            if "voyager/news" in response.text or response.status_code == 302:
                print("🌐 Новость успешно опубликована на сайте!")
                return True
            else:
                print("⚠️ Ответ не подтверждает успешное добавление.")
                # Проверяем на наличие сообщений об успехе
                success_keywords = ['успех', 'создан', 'добавлен', 'success', 'created', 'added']
                if any(keyword in response.text.lower() for keyword in success_keywords):
                    print("✅ Похоже, новость добавлена успешно (найдены ключевые слова)")
                    return True

                # Проверяем наличие ошибок валидации
                error_keywords = ['error', 'ошибка', 'validation', 'валидация']
                if any(keyword in response.text.lower() for keyword in error_keywords):
                    print("❌ Найдены ошибки в ответе")
                    # Ищем конкретные ошибки
                    soup = BeautifulSoup(response.text, "html.parser")
                    errors = soup.find_all(class_=['error', 'alert-danger', 'validation-error'])
                    for error in errors:
                        print(f"Ошибка: {error.get_text(strip=True)}")

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