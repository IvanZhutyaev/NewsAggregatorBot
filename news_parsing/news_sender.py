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
admin_message_ids = {}  # Для хранения ID всех сообщений новости по admin_id


async def send_raw_news_to_admin(title: str, news_text: str, source_url: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            news_id = hashlib.md5(source_url.encode()).hexdigest()
            pending_raw_news[news_id] = {
                "url": source_url,
                "title": title,
                "text": news_text
            }

            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="✅ Одобрить для редактирования", callback_data=f"approve_raw|{news_id}")
            keyboard.button(text="❌ Отклонить", callback_data=f"reject_raw|{news_id}")

            # Создаем ОДНО сообщение со всей информацией
            message_text = (
                f"<b>📰 Сырая новость</b>\n\n"
                f"<b>📝 Заголовок:</b>\n{title}\n\n"
                f"<b>📄 Текст новости:</b>\n{news_text}\n\n"
                f"<b>🔗 Источник:</b>\n{source_url}"
            )

            # Отправляем ВСЕМ админам
            sent_to_admins = 0
            for admin_id in ADMINS:
                try:
                    # Инициализируем хранилище сообщений для этого admin_id и news_id
                    if admin_id not in admin_message_ids:
                        admin_message_ids[admin_id] = {}

                    message_ids = []

                    # Отправляем ОДНО текстовое сообщение с кнопками
                    text_message = await bot.send_message(
                        admin_id,
                        message_text,
                        reply_markup=keyboard.as_markup(),
                        parse_mode="HTML"
                    )
                    message_ids.append(text_message.message_id)

                    # Сохраняем все ID сообщений для этой новости
                    admin_message_ids[admin_id][news_id] = message_ids

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
async def send_processed_news_to_admin(news_text: str, source_url: str, original_title: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Добавляем случайное изображение для финальной публикации
            import os
            import random
            image_files = os.listdir("images")
            image_path = os.path.join("images", random.choice(image_files)) if image_files else None

            news_id = hashlib.md5(f"{source_url}_processed".encode()).hexdigest()
            pending_processed_news[news_id] = {
                "url": source_url,
                "text": news_text,
                "image": image_path  # Добавляем image для публикации
            }

            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🌐 На сайт", callback_data=f"site|{news_id}")
            keyboard.button(text="✅ В Telegram", callback_data=f"approve|{news_id}")
            keyboard.button(text="🚀 Оба", callback_data=f"both|{news_id}")
            keyboard.button(text="❌ Отклонить", callback_data=f"reject|{news_id}")

            # Создаем ОДНО сообщение со всей информацией
            message_text = (
                f"<b>✍️ Обработанная новость</b>\n\n"
                f"<b>📝 Оригинальный заголовок:</b>\n{original_title}\n\n"
                f"<b>📄 Обработанный текст:</b>\n{news_text}\n\n"
                f"<b>🔗 Источник:</b>\n{source_url}"
            )

            # Отправляем ВСЕМ админам
            sent_to_admins = 0
            for admin_id in ADMINS:
                try:
                    # Инициализируем хранилище сообщений для этого admin_id и news_id
                    if admin_id not in admin_message_ids:
                        admin_message_ids[admin_id] = {}

                    message_ids = []

                    # Отправляем ОДНО текстовое сообщение с кнопками
                    text_message = await bot.send_message(
                        admin_id,
                        message_text,
                        reply_markup=keyboard.as_markup(),
                        parse_mode="HTML"
                    )
                    message_ids.append(text_message.message_id)

                    # Сохраняем все ID сообщений для этой новости
                    admin_message_ids[admin_id][news_id] = message_ids

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
async def delete_news_messages(admin_id: int, news_id: str):
    """Удаляет все сообщения связанные с конкретной новостью у админа"""
    try:
        if admin_id in admin_message_ids and news_id in admin_message_ids[admin_id]:
            message_ids = admin_message_ids[admin_id][news_id]
            deleted_count = 0

            for message_id in message_ids:
                try:
                    await bot.delete_message(admin_id, message_id)
                    deleted_count += 1
                    await asyncio.sleep(0.1)  # Небольшая задержка между удалениями
                except Exception as e:
                    print(f"⚠️ Не удалось удалить сообщение {message_id}: {e}")

            # Удаляем запись о сообщениях
            del admin_message_ids[admin_id][news_id]
            print(f"✅ Удалено {deleted_count} сообщений новости у админа {admin_id}")

    except Exception as e:
        print(f"❌ Ошибка при удалении сообщений новости: {e}")


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