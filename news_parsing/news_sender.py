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

            # Создаем базовое сообщение с заголовком и ссылкой
            base_caption = f"<b>{title}</b>\n\n🔗 Источник: {source_url}"

            # Отправляем ВСЕМ админам
            sent_to_admins = 0
            for admin_id in ADMINS:
                try:
                    # Инициализируем хранилище сообщений для этого admin_id и news_id
                    if admin_id not in admin_message_ids:
                        admin_message_ids[admin_id] = {}

                    message_ids = []

                    # Сначала отправляем фото с заголовком
                    photo_message = await bot.send_photo(
                        admin_id,
                        photo,
                        caption=base_caption,
                        reply_markup=keyboard.as_markup(),
                        parse_mode="HTML"
                    )
                    message_ids.append(photo_message.message_id)

                    # Затем отправляем текст новости частями (если он есть)
                    if news_text and len(news_text.strip()) > 0:
                        text_message_ids = await send_long_message(admin_id, news_text, "📝 Текст новости:")
                        message_ids.extend(text_message_ids)

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

            # Создаем базовое сообщение
            base_caption = f"✍️ <b>Обработанная новость</b>\n(оригинал: {original_title})"

            # Отправляем ВСЕМ админам
            sent_to_admins = 0
            for admin_id in ADMINS:
                try:
                    # Инициализируем хранилище сообщений для этого admin_id и news_id
                    if admin_id not in admin_message_ids:
                        admin_message_ids[admin_id] = {}

                    message_ids = []

                    # Сначала отправляем фото с заголовком
                    photo_message = await bot.send_photo(
                        admin_id,
                        photo,
                        caption=base_caption,
                        reply_markup=keyboard.as_markup(),
                        parse_mode="HTML"
                    )
                    message_ids.append(photo_message.message_id)

                    # Затем отправляем обработанный текст частями
                    if news_text and len(news_text.strip()) > 0:
                        text_message_ids = await send_long_message(admin_id, news_text, "📄 Обработанный текст:")
                        message_ids.extend(text_message_ids)

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


async def send_long_message(chat_id: int, text: str, prefix: str = ""):
    """
    Отправляет длинное сообщение частями и возвращает ID сообщений
    """
    # Максимальная длина сообщения в Telegram
    MAX_MESSAGE_LENGTH = 4096

    message_ids = []

    if not text or len(text) <= MAX_MESSAGE_LENGTH:
        # Если текст короткий, отправляем как есть
        message = f"{prefix}\n\n{text}" if prefix else text
        sent_message = await bot.send_message(chat_id, message, parse_mode="HTML")
        message_ids.append(sent_message.message_id)
        return message_ids

    # Разбиваем текст на части
    parts = []
    current_part = ""

    # Разбиваем по абзацам, чтобы не обрывать слова
    paragraphs = text.split('\n\n')

    for paragraph in paragraphs:
        # Если добавление параграфа не превысит лимит
        if len(current_part) + len(paragraph) + 2 <= MAX_MESSAGE_LENGTH:
            if current_part:
                current_part += '\n\n' + paragraph
            else:
                current_part = paragraph
        else:
            # Если текущая часть не пустая, сохраняем её
            if current_part:
                parts.append(current_part)

            # Если параграф сам по себе слишком длинный, разбиваем его
            if len(paragraph) > MAX_MESSAGE_LENGTH:
                # Разбиваем на предложения
                sentences = paragraph.split('. ')
                current_part = ""
                for sentence in sentences:
                    if len(current_part) + len(sentence) + 2 <= MAX_MESSAGE_LENGTH:
                        if current_part:
                            current_part += '. ' + sentence
                        else:
                            current_part = sentence
                    else:
                        if current_part:
                            parts.append(current_part)
                        current_part = sentence
                # Добавляем последнюю накопленную часть
                if current_part:
                    parts.append(current_part)
                    current_part = ""
            else:
                current_part = paragraph

    # Добавляем последнюю часть
    if current_part:
        parts.append(current_part)

    # Отправляем части с задержкой между сообщениями
    for i, part in enumerate(parts, 1):
        try:
            if i == 1 and prefix:
                message = f"{prefix}\n\n{part}"
            else:
                message = part

            sent_message = await bot.send_message(chat_id, message, parse_mode="HTML")
            message_ids.append(sent_message.message_id)

            # Небольшая задержка между сообщениями
            if i < len(parts):
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"❌ Ошибка отправки части {i}/{len(parts)}: {e}")

    return message_ids


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