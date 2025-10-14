import requests
from bs4 import BeautifulSoup
from config import SITE_URL, SITE_LOGIN, SITE_PASSWORD

session = requests.Session()

def login_to_site():
    """Авторизация в админ-панели сайта"""
    login_url = f"{SITE_URL}/admin/login"
    data = {
        "username": SITE_LOGIN,
        "password": SITE_PASSWORD
    }
    try:
        response = session.post(login_url, data=data, timeout=10)
        if response.status_code == 200 and "logout" in response.text.lower():
            print("✅ Авторизация на сайте прошла успешно")
            return True
        else:
            print("⚠️ Не удалось войти в админ-панель")
            return False
    except Exception as e:
        print(f"❌ Ошибка авторизации: {e}")
        return False


def extract_title_and_body(text: str):
    """Извлекает заголовок и тело новости (разделены пустой строкой)"""
    parts = text.strip().split("\n\n", 1)
    title = parts[0].strip()
    body = parts[1].strip() if len(parts) > 1 else ""
    return title, body


def post_news_to_site(news_text: str, image_path: str = None):
    """Публикация новости на сайт"""
    if not login_to_site():
        return False

    create_url = f"{SITE_URL}/admin/news/create"

    title, body = extract_title_and_body(news_text)

    # SEO-поля можно просто дублировать заголовок и часть текста
    seo_title = title
    seo_description = body[:160]
    seo_keywords = ", ".join(title.split()[:5])

    data = {
        "title_ru": title,
        "subtitle_ru": title,  # можно дублировать заголовок
        "description_ru": body,
        "seo_title_ru": seo_title,
        "seo_description_ru": seo_description,
        "seo_keywords_ru": seo_keywords,
        "seo_url": "",
    }

    files = {}
    if image_path:
        try:
            files["image"] = open(image_path, "rb")
        except Exception as e:
            print(f"⚠️ Не удалось прикрепить изображение: {e}")

    try:
        response = session.post(create_url, data=data, files=files, timeout=15)

        if files:
            files["image"].close()

        if response.status_code == 200:
            # Проверим, вернулся ли успех (по HTML)
            if "успешно" in response.text.lower() or "success" in response.text.lower():
                print("🌐 Новость успешно опубликована на сайте")
                return True
            else:
                print("⚠️ Ответ без признаков успеха. Проверь HTML вручную.")
                soup = BeautifulSoup(response.text, "html.parser")
                print(soup.title.text if soup.title else response.text[:500])
        else:
            print(f"❌ Ошибка при отправке: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка отправки на сайт: {e}")

    return False
