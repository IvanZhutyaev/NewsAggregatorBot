import requests
from bs4 import BeautifulSoup
from config import SITE_URL, SITE_LOGIN, SITE_PASSWORD

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
    parts = text.strip().split("\n\n", 1)
    title = parts[0].strip()
    body = parts[1].strip() if len(parts) > 1 else ""
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

    data = {
        "_token": csrf_token,
        "title_ru": title,
        "subtitle_ru": title,
        "description_ru": body,
        "seo_title_ru": title,
        "seo_description_ru": body[:160],
        "seo_keywords_ru": ", ".join(title.split()[:5]),
        "seo_url": "",
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

        if response.status_code in (200, 302):
            if "voyager/news" in response.text or response.status_code == 302:
                print("🌐 Новость успешно опубликована на сайте!")
                return True
            else:
                print("⚠️ Ответ не подтверждает успешное добавление. Проверь HTML:")
                soup = BeautifulSoup(response.text, "html.parser")
                title_tag = soup.title.text if soup.title else "Нет тега <title>"
                print("Ответ страницы:", title_tag)
        else:
            print(f"❌ Ошибка публикации: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка при отправке новости: {e}")

    return False
