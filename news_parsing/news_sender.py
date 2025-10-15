import asyncio
import os
import random
import hashlib
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError
from config import BOT_TOKEN, ADMINS

bot = Bot(token=BOT_TOKEN)

# Глобальные словари для хранения состояний
pending_raw_news = {}  # Для сырых новостей на одобрение
pending_processed_news = {}  # Для обработанных новостей на финальную публикацию


# Отправка сырой новости на первичное одобрение
async def send_raw_news_to_admin(title: str, news_text: str, source_url: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            image_files = os.listdir("images")
            if not image_files:
                print("❌ Нет изображений в папке images")
                return

            image_path = os.path.join("images", random.choice(image_files))
            news_id = hashlib.md5(source_url.encode()).hexdigest()
            pending_raw_news[news_id] = {
                "url": source_url,
                "image": image_path,
                "title": title,
                "text": news_text
            }

            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="✅ Одобрить для редактирования", callback_data=f"approve_raw|{news_id}")
            keyboard.button(text="❌ Отклонить", callback_data=f"reject_raw|{news_id}")

            photo = FSInputFile(image_path)
            admin_caption = f"<b>{title}</b>\n\n{news_text}\n\n🔗 Источник: {source_url}"

            # Отправляем ВСЕМ админам
            sent_to_admins = 0
            for admin_id in ADMINS:
                try:
                    if len(admin_caption) <= 1024:
                        await bot.send_photo(
                            admin_id,
                            photo,
                            caption=admin_caption,
                            reply_markup=keyboard.as_markup(),
                            parse_mode="HTML"
                        )
                    else:
                        await bot.send_photo(
                            admin_id,
                            photo,
                            caption=f"<b>{title}</b>\n\n🔗 Источник: {source_url}",
                            reply_markup=keyboard.as_markup(),
                            parse_mode="HTML"
                        )
                        await bot.send_message(admin_id, news_text)
                    print(f"✅ Сырая новость отправлена админу {admin_id}")
                    sent_to_admins += 1
                except TelegramForbiddenError:
                    print(f"❌ Не удалось отправить админу {admin_id} — он не написал боту.")
                except Exception as e:
                    print(f"❌ Ошибка отправки админу {admin_id}: {e}")

            if sent_to_admins > 0:
                print(f"📨 Сырая новость отправлена {sent_to_admins} админам")
                break

        except TelegramNetworkError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⚠️ Ошибка сети, повторная попытка {attempt + 1} через {wait_time} сек...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ Не удалось отправить сырую новость после {max_retries} попыток: {e}")
        except Exception as e:
            print(f"❌ Критическая ошибка в send_raw_news_to_admin: {e}")
            break


# Отправка обработанной новости на финальное одобрение
async def send_processed_news_to_admin(news_text: str, source_url: str, original_title: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            image_files = os.listdir("images")
            if not image_files:
                print("❌ Нет изображений в папке images")
                return

            image_path = os.path.join("images", random.choice(image_files))
            news_id = hashlib.md5(f"{source_url}_processed".encode()).hexdigest()
            pending_processed_news[news_id] = {
                "url": source_url,
                "image": image_path,
                "text": news_text
            }

            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🌐 На сайт", callback_data=f"site|{news_id}")
            keyboard.button(text="✅ В Telegram", callback_data=f"approve|{news_id}")
            keyboard.button(text="🚀 Оба", callback_data=f"both|{news_id}")
            keyboard.button(text="❌ Отклонить", callback_data=f"reject|{news_id}")

            photo = FSInputFile(image_path)
            admin_caption = f"✍️ <b>Обработанная новость</b>\n(оригинал: {original_title})\n\n{news_text}"

            # Отправляем ВСЕМ админам
            sent_to_admins = 0
            for admin_id in ADMINS:
                try:
                    if len(admin_caption) <= 1024:
                        await bot.send_photo(
                            admin_id,
                            photo,
                            caption=admin_caption,
                            reply_markup=keyboard.as_markup(),
                            parse_mode="HTML"
                        )
                    else:
                        await bot.send_photo(
                            admin_id,
                            photo,
                            caption=f"✍️ <b>Обработанная новость</b>\n(оригинал: {original_title})",
                            reply_markup=keyboard.as_markup(),
                            parse_mode="HTML"
                        )
                        await bot.send_message(admin_id, news_text, parse_mode="HTML")
                    print(f"✅ Обработанная новость отправлена админу {admin_id}")
                    sent_to_admins += 1
                except TelegramForbiddenError:
                    print(f"❌ Не удалось отправить админу {admin_id} — он не написал боту.")
                except Exception as e:
                    print(f"❌ Ошибка отправки админу {admin_id}: {e}")

            if sent_to_admins > 0:
                print(f"📨 Обработанная новость отправлена {sent_to_admins} админам")
                break

        except TelegramNetworkError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⚠️ Ошибка сети, повторная попытка {attempt + 1} через {wait_time} сек...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ Не удалось отправить обработанную новость после {max_retries} попыток: {e}")
        except Exception as e:
            print(f"❌ Критическая ошибка в send_processed_news_to_admin: {e}")
            break


# Геттеры для доступа к данным из других модулей
def get_pending_raw_news():
    return pending_raw_news

def get_pending_processed_news():
    return pending_processed_news

def remove_from_pending_raw_news(news_id):
    if news_id in pending_raw_news:
        pending_raw_news.pop(news_id, None)

def remove_from_pending_processed_news(news_id):
    if news_id in pending_processed_news:
        pending_processed_news.pop(news_id, None)