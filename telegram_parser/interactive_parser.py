"""
Интерактивный парсер Telegram чатов
- Выбор чатов из списка
- Фильтр по датам
- Расшифровка голосовых (Telegram Premium)
- Разбивка по датам
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from telethon import TelegramClient
from telethon.tl.types import Message, User, Channel, Chat, DocumentAttributeAudio
from telethon.tl.functions.messages import TranscribeAudioRequest
from telethon.errors import FloodWaitError
from dotenv import load_dotenv

load_dotenv()

# Конфигурация
API_ID = int(os.getenv("TELEGRAM_API_ID", "34895963"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "172b6659e5de8862f012ce4326038383")
PHONE = os.getenv("TELEGRAM_PHONE", "+79629403333")
SESSION_NAME = "telegram_parser_session"

# Период по умолчанию
DEFAULT_START = datetime(2025, 1, 15)
DEFAULT_END = datetime(2025, 2, 1, 23, 59, 59)


async def get_voice_transcription(client, message):
    """Получить расшифровку голосового сообщения"""
    try:
        # Проверяем, есть ли уже расшифровка
        if hasattr(message, 'voice_transcription') and message.voice_transcription:
            return message.voice_transcription

        # Пробуем запросить расшифровку через API
        result = await client(TranscribeAudioRequest(
            peer=message.peer_id,
            msg_id=message.id
        ))

        if result and hasattr(result, 'text'):
            return result.text

        # Ждём завершения расшифровки
        await asyncio.sleep(2)

        # Получаем обновлённое сообщение
        updated = await client.get_messages(message.peer_id, ids=message.id)
        if updated and hasattr(updated, 'voice_transcription'):
            return updated.voice_transcription

    except Exception as e:
        if "PREMIUM" in str(e).upper():
            return "[Требуется Premium для расшифровки]"
        return f"[Ошибка расшифровки: {e}]"

    return None


def is_voice_message(message):
    """Проверить, является ли сообщение голосовым"""
    if not message.media:
        return False
    if not hasattr(message.media, 'document') or not message.media.document:
        return False
    for attr in message.media.document.attributes:
        if isinstance(attr, DocumentAttributeAudio) and attr.voice:
            return True
    return False


async def main():
    print("=" * 50)
    print("  TELEGRAM CHAT PARSER")
    print("=" * 50)

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start(phone=PHONE)

    me = await client.get_me()
    print(f"\n✓ Авторизован: {me.first_name} (@{me.username})\n")

    # Получаем список диалогов
    print("Загрузка списка чатов...")
    dialogs = await client.get_dialogs(limit=50)

    print("\n" + "=" * 50)
    print("  ВАШИ ЧАТЫ:")
    print("=" * 50)

    chat_list = []
    for i, dialog in enumerate(dialogs, 1):
        chat_type = "👤" if isinstance(dialog.entity, User) else "👥" if isinstance(dialog.entity, Chat) else "📢"
        print(f"  {i:2}. {chat_type} {dialog.name}")
        chat_list.append(dialog)

    print("=" * 50)

    # Выбор чатов
    print("\nВведите номера чатов через запятую (например: 1,3,5)")
    print("Или 'all' для всех, или Enter для отмены:")

    choice = input("> ").strip()

    if not choice:
        print("Отменено.")
        await client.disconnect()
        return

    selected_dialogs = []
    if choice.lower() == 'all':
        selected_dialogs = chat_list
    else:
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected_dialogs = [chat_list[i] for i in indices if 0 <= i < len(chat_list)]
        except:
            print("Ошибка ввода!")
            await client.disconnect()
            return

    if not selected_dialogs:
        print("Чаты не выбраны.")
        await client.disconnect()
        return

    print(f"\nВыбрано чатов: {len(selected_dialogs)}")
    for d in selected_dialogs:
        print(f"  - {d.name}")

    # Даты
    print(f"\nПериод по умолчанию: {DEFAULT_START.strftime('%d.%m.%Y')} - {DEFAULT_END.strftime('%d.%m.%Y')}")
    print("Нажмите Enter для использования или введите свои даты (ДД.ММ.ГГГГ-ДД.ММ.ГГГГ):")

    date_input = input("> ").strip()

    start_date = DEFAULT_START
    end_date = DEFAULT_END

    if date_input:
        try:
            parts = date_input.split("-")
            start_date = datetime.strptime(parts[0].strip(), "%d.%m.%Y")
            end_date = datetime.strptime(parts[1].strip(), "%d.%m.%Y").replace(hour=23, minute=59, second=59)
        except:
            print("Ошибка формата дат, используются даты по умолчанию")

    print(f"\nПарсинг с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}")

    # Расшифровка голосовых?
    print("\nРасшифровывать голосовые сообщения? (y/n, по умолчанию: y)")
    transcribe = input("> ").strip().lower() != 'n'

    # Создаём папку для результатов
    output_dir = Path("output") / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nРезультаты будут сохранены в: {output_dir}")
    print("\n" + "=" * 50)
    print("  НАЧИНАЕМ ПАРСИНГ...")
    print("=" * 50 + "\n")

    # Парсим каждый чат
    for dialog in selected_dialogs:
        chat_name = dialog.name.replace("/", "_").replace("\\", "_")[:50]
        print(f"\n📂 Чат: {dialog.name}")

        messages_by_date = defaultdict(list)
        voice_count = 0
        total_count = 0

        try:
            async for message in client.iter_messages(
                dialog.entity,
                offset_date=end_date,
                reverse=False
            ):
                if not isinstance(message, Message):
                    continue

                # Проверяем дату
                if message.date:
                    msg_date = message.date.replace(tzinfo=None)
                    if msg_date < start_date:
                        break
                    if msg_date > end_date:
                        continue

                total_count += 1
                if total_count % 100 == 0:
                    print(f"   Обработано: {total_count}...")

                # Получаем отправителя
                sender_name = "Unknown"
                try:
                    sender = await message.get_sender()
                    if sender:
                        if isinstance(sender, User):
                            sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                            if sender.username:
                                sender_name += f" (@{sender.username})"
                        else:
                            sender_name = getattr(sender, 'title', 'Unknown')
                except:
                    pass

                # Текст сообщения
                text = message.text or message.message or ""

                # Проверяем голосовое
                voice_text = None
                if is_voice_message(message):
                    voice_count += 1
                    if transcribe:
                        voice_text = await get_voice_transcription(client, message)
                        if voice_text:
                            text = f"[🎤 Голосовое]: {voice_text}"
                        else:
                            text = "[🎤 Голосовое сообщение]"
                    else:
                        text = "[🎤 Голосовое сообщение]"

                # Формируем данные
                date_key = message.date.strftime("%Y-%m-%d")
                msg_data = {
                    "id": message.id,
                    "time": message.date.strftime("%H:%M:%S"),
                    "datetime": message.date.isoformat(),
                    "sender": sender_name,
                    "text": text,
                    "is_voice": is_voice_message(message),
                    "voice_transcription": voice_text,
                    "has_media": bool(message.media),
                    "reply_to": message.reply_to.reply_to_msg_id if message.reply_to else None,
                }

                messages_by_date[date_key].append(msg_data)

        except FloodWaitError as e:
            print(f"   ⚠️ Лимит запросов, ждём {e.seconds} сек...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")

        print(f"   ✓ Собрано: {total_count} сообщений, {voice_count} голосовых")

        # Сохраняем по датам
        chat_dir = output_dir / chat_name
        chat_dir.mkdir(exist_ok=True)

        # Общий файл
        all_messages = []
        for date_key in sorted(messages_by_date.keys()):
            all_messages.extend(sorted(messages_by_date[date_key], key=lambda x: x["datetime"]))

        with open(chat_dir / "all_messages.json", "w", encoding="utf-8") as f:
            json.dump(all_messages, f, ensure_ascii=False, indent=2)

        # Файлы по датам
        for date_key, messages in messages_by_date.items():
            messages_sorted = sorted(messages, key=lambda x: x["datetime"])

            # JSON
            with open(chat_dir / f"{date_key}.json", "w", encoding="utf-8") as f:
                json.dump(messages_sorted, f, ensure_ascii=False, indent=2)

            # Текстовый файл (читаемый)
            with open(chat_dir / f"{date_key}.txt", "w", encoding="utf-8") as f:
                f.write(f"{'=' * 50}\n")
                f.write(f"  {dialog.name}\n")
                f.write(f"  Дата: {date_key}\n")
                f.write(f"  Сообщений: {len(messages_sorted)}\n")
                f.write(f"{'=' * 50}\n\n")

                for msg in messages_sorted:
                    f.write(f"[{msg['time']}] {msg['sender']}:\n")
                    f.write(f"  {msg['text']}\n\n")

        print(f"   💾 Сохранено в: {chat_dir}")

    print("\n" + "=" * 50)
    print(f"  ГОТОВО! Результаты в: {output_dir}")
    print("=" * 50)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
