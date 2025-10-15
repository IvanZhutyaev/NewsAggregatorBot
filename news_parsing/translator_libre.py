import requests
import time

LIBRE_SERVERS = [
    "https://libretranslate.de/translate",
    "https://translate.argosopentech.com/translate",
]

def translate_text(text: str, target_lang: str, source_lang: str = "ru") -> str:
    if not text.strip():
        return text

    payload = {
        "q": text,
        "source": source_lang,
        "target": target_lang,
        "format": "text",
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "AgrocomplexNewsBot/1.0"
    }

    for url in LIBRE_SERVERS:
        try:
            print(f"🔄 Переводим через {url} → {target_lang}")
            response = requests.post(url, data=payload, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"⚠️ LibreTranslate ответил {response.status_code}")
                continue
            data = response.json()
            if "translatedText" in data:
                text_tr = data["translatedText"]
                print(f"✅ Переведено ({target_lang}): {len(text_tr)} символов")
                time.sleep(1)
                return text_tr
        except Exception as e:
            print(f"⚠️ Ошибка LibreTranslate ({url}): {e}")
            continue

    # --- Fallback: MyMemory API ---
    try:
        print(f"🪄 Используем запасной переводчик (MyMemory API)...")
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text, "langpair": f"{source_lang}|{target_lang}"}
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        text_tr = data["responseData"]["translatedText"]
        print(f"✅ Переведено через MyMemory ({target_lang})")
        return text_tr
    except Exception as e:
        print(f"❌ Ошибка резервного перевода ({target_lang}): {e}")
        return text
