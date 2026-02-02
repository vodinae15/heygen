"""
Telegram Chat Parser - парсинг всех сообщений из чата
Использует Telethon для работы с Telegram API
"""

import asyncio
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from telethon import TelegramClient
from telethon.tl.types import (
    Message,
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
    User,
    Channel,
    Chat,
    PeerChannel,
    PeerChat,
    InputPeerChannel,
)
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.errors import (
    SessionPasswordNeededError,
    FloodWaitError,
    ChatAdminRequiredError,
    ChannelPrivateError,
)

from config import Config


class TelegramChatParser:
    """Класс для парсинга сообщений из Telegram чатов"""

    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[TelegramClient] = None
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def connect(self) -> bool:
        """Подключение к Telegram"""
        self.client = TelegramClient(
            self.config.session_name,
            self.config.api_id,
            self.config.api_hash
        )

        await self.client.start(phone=self.config.phone_number)

        if not await self.client.is_user_authorized():
            print("Требуется авторизация. Введите код из Telegram.")
            return False

        me = await self.client.get_me()
        print(f"Авторизован как: {me.first_name} (@{me.username})")
        return True

    async def disconnect(self):
        """Отключение от Telegram"""
        if self.client:
            await self.client.disconnect()

    async def find_chat_by_id(self, chat_id: int):
        """Найти чат по ID через диалоги"""
        # Пробуем разные варианты ID
        ids_to_try = [chat_id, -chat_id, int(f"-100{abs(chat_id)}")]

        print(f"Загрузка диалогов для поиска чата...")
        async for dialog in self.client.iter_dialogs():
            entity_id = dialog.entity.id
            # Проверяем совпадение ID
            if entity_id in ids_to_try or abs(entity_id) == abs(chat_id):
                print(f"Найден чат: {dialog.name} (ID: {entity_id})")
                return dialog.entity

        return None

    async def get_chat_info(self, chat_identifier: str) -> Dict[str, Any]:
        """Получить информацию о чате"""
        try:
            entity = None
            # Если это число - ищем через диалоги
            try:
                chat_id = int(chat_identifier)
                entity = await self.find_chat_by_id(chat_id)
            except ValueError:
                pass

            if not entity:
                entity = await self.client.get_entity(chat_identifier)

            info = {
                "id": entity.id,
                "type": type(entity).__name__,
            }

            if isinstance(entity, User):
                info.update({
                    "first_name": entity.first_name,
                    "last_name": entity.last_name,
                    "username": entity.username,
                    "phone": entity.phone,
                })
            elif isinstance(entity, (Channel, Chat)):
                info.update({
                    "title": entity.title,
                    "username": getattr(entity, 'username', None),
                    "participants_count": getattr(entity, 'participants_count', None),
                })

            return info
        except Exception as e:
            print(f"Ошибка получения информации о чате: {e}")
            return {}

    def _extract_media_info(self, message: Message) -> Optional[Dict[str, Any]]:
        """Извлечь информацию о медиа из сообщения"""
        if not message.media:
            return None

        media_info = {"type": type(message.media).__name__}

        if isinstance(message.media, MessageMediaPhoto):
            media_info["type"] = "photo"
            if message.media.photo:
                media_info["id"] = message.media.photo.id

        elif isinstance(message.media, MessageMediaDocument):
            doc = message.media.document
            if doc:
                media_info.update({
                    "type": "document",
                    "id": doc.id,
                    "mime_type": doc.mime_type,
                    "size": doc.size,
                })
                # Определяем тип документа
                for attr in doc.attributes:
                    attr_type = type(attr).__name__
                    if attr_type == "DocumentAttributeFilename":
                        media_info["filename"] = attr.file_name
                    elif attr_type == "DocumentAttributeVideo":
                        media_info["type"] = "video"
                        media_info["duration"] = attr.duration
                        media_info["width"] = attr.w
                        media_info["height"] = attr.h
                    elif attr_type == "DocumentAttributeAudio":
                        media_info["type"] = "audio" if not attr.voice else "voice"
                        media_info["duration"] = attr.duration
                    elif attr_type == "DocumentAttributeSticker":
                        media_info["type"] = "sticker"
                        media_info["emoji"] = attr.alt
                    elif attr_type == "DocumentAttributeAnimated":
                        media_info["type"] = "animation"

        elif isinstance(message.media, MessageMediaWebPage):
            if message.media.webpage:
                webpage = message.media.webpage
                if hasattr(webpage, 'url'):
                    media_info.update({
                        "type": "webpage",
                        "url": webpage.url,
                        "title": getattr(webpage, 'title', None),
                        "description": getattr(webpage, 'description', None),
                    })

        return media_info

    async def _get_sender_info(self, message: Message) -> Dict[str, Any]:
        """Получить информацию об отправителе"""
        sender_info = {"id": None, "name": None, "username": None}

        try:
            sender = await message.get_sender()
            if sender:
                sender_info["id"] = sender.id
                if isinstance(sender, User):
                    sender_info["name"] = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                    sender_info["username"] = sender.username
                elif isinstance(sender, (Channel, Chat)):
                    sender_info["name"] = sender.title
                    sender_info["username"] = getattr(sender, 'username', None)
        except Exception:
            pass

        return sender_info

    async def parse_messages(
        self,
        chat_identifier: str,
        limit: Optional[int] = None,
        offset_date: Optional[datetime] = None,
        min_id: int = 0,
        max_id: int = 0,
        search: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Парсинг сообщений из чата

        Args:
            chat_identifier: ID чата, username или ссылка
            limit: Максимальное количество сообщений (None = все)
            offset_date: Парсить сообщения до этой даты
            min_id: Минимальный ID сообщения
            max_id: Максимальный ID сообщения
            search: Поисковый запрос
            start_date: Начальная дата (сообщения после этой даты)
            end_date: Конечная дата (сообщения до этой даты)

        Returns:
            Список сообщений в виде словарей
        """
        messages_data = []

        try:
            # Пытаемся найти entity
            entity = None

            # Если это число - ищем через диалоги
            try:
                chat_id = int(chat_identifier)
                entity = await self.find_chat_by_id(chat_id)
            except ValueError:
                pass

            # Если не нашли через диалоги - пробуем напрямую
            if not entity:
                try:
                    entity = await self.client.get_entity(chat_identifier)
                except ValueError:
                    # Последняя попытка - поиск по имени в диалогах
                    async for dialog in self.client.iter_dialogs():
                        if chat_identifier.lower() in dialog.name.lower():
                            entity = dialog.entity
                            break

            if not entity:
                raise ValueError(f"Чат не найден: {chat_identifier}")

            print(f"Парсинг чата: {getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')}")

            # Используем end_date как offset_date для API
            effective_offset_date = end_date or offset_date

            # Параметры для iter_messages
            iter_params = {
                "entity": entity,
                "limit": limit,
                "offset_date": effective_offset_date,
                "min_id": min_id,
                "max_id": max_id,
                "search": search,
            }

            count = 0
            skipped = 0
            async for message in self.client.iter_messages(**iter_params):
                if not isinstance(message, Message):
                    continue

                # Фильтрация по start_date - пропускаем старые сообщения
                if start_date and message.date:
                    msg_date = message.date.replace(tzinfo=None)
                    if msg_date < start_date:
                        skipped += 1
                        # Прекращаем если вышли за пределы диапазона
                        break

                count += 1
                if count % 100 == 0:
                    print(f"Обработано {count} сообщений...")

                # Извлекаем данные сообщения
                sender_info = await self._get_sender_info(message)
                media_info = self._extract_media_info(message)

                # Извлекаем ID пересылки (может быть PeerUser/PeerChannel объектом)
                forward_from_id = None
                if message.fwd_from and message.fwd_from.from_id:
                    fwd = message.fwd_from.from_id
                    forward_from_id = getattr(fwd, 'user_id', None) or getattr(fwd, 'channel_id', None) or getattr(fwd, 'chat_id', None)

                message_data = {
                    "id": message.id,
                    "date": message.date.isoformat() if message.date else None,
                    "text": message.text or message.message or "",
                    "sender_id": sender_info["id"],
                    "sender_name": sender_info["name"],
                    "sender_username": sender_info["username"],
                    "reply_to_msg_id": message.reply_to.reply_to_msg_id if message.reply_to else None,
                    "forward_from_id": forward_from_id,
                    "views": message.views,
                    "forwards": message.forwards,
                    "reactions": None,
                    "media": media_info,
                    "edit_date": message.edit_date.isoformat() if message.edit_date else None,
                    "is_pinned": message.pinned,
                }

                # Обработка реакций
                if message.reactions:
                    reactions_list = []
                    for reaction in message.reactions.results:
                        reactions_list.append({
                            "emoji": getattr(reaction.reaction, 'emoticon', str(reaction.reaction)),
                            "count": reaction.count,
                        })
                    message_data["reactions"] = reactions_list

                messages_data.append(message_data)

            print(f"Всего собрано {len(messages_data)} сообщений")
            if start_date or end_date:
                print(f"(в диапазоне дат: {start_date or 'начало'} - {end_date or 'сейчас'})")

        except FloodWaitError as e:
            print(f"Превышен лимит запросов. Подождите {e.seconds} секунд.")
            raise
        except ChatAdminRequiredError:
            print("Недостаточно прав для доступа к чату")
            raise
        except ChannelPrivateError:
            print("Чат приватный, нет доступа")
            raise
        except Exception as e:
            print(f"Ошибка при парсинге: {e}")
            raise

        return messages_data

    def save_to_json(self, messages: List[Dict[str, Any]], filename: str):
        """Сохранить сообщения в JSON файл"""
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        print(f"Сохранено в {filepath}")

    def save_to_csv(self, messages: List[Dict[str, Any]], filename: str):
        """Сохранить сообщения в CSV файл"""
        if not messages:
            print("Нет сообщений для сохранения")
            return

        filepath = self.output_dir / filename

        # Преобразуем вложенные структуры в строки
        flat_messages = []
        for msg in messages:
            flat_msg = msg.copy()
            flat_msg["media"] = json.dumps(msg["media"], ensure_ascii=False) if msg["media"] else ""
            flat_msg["reactions"] = json.dumps(msg["reactions"], ensure_ascii=False) if msg["reactions"] else ""
            flat_messages.append(flat_msg)

        fieldnames = flat_messages[0].keys()

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_messages)

        print(f"Сохранено в {filepath}")

    async def download_media(self, messages: List[Dict[str, Any]], chat_identifier: str):
        """Скачать медиа файлы из сообщений"""
        media_dir = self.output_dir / "media"
        media_dir.mkdir(exist_ok=True)

        entity = await self.client.get_entity(chat_identifier)

        downloaded = 0
        for msg_data in messages:
            if not msg_data.get("media"):
                continue

            try:
                message = await self.client.get_messages(entity, ids=msg_data["id"])
                if message and message.media:
                    path = await self.client.download_media(
                        message,
                        file=str(media_dir / f"{msg_data['id']}")
                    )
                    if path:
                        downloaded += 1
                        if downloaded % 10 == 0:
                            print(f"Скачано {downloaded} медиа файлов...")
            except Exception as e:
                print(f"Ошибка скачивания медиа {msg_data['id']}: {e}")

        print(f"Всего скачано {downloaded} медиа файлов в {media_dir}")


async def main():
    """Основная функция"""
    config = Config()
    parser = TelegramChatParser(config)

    try:
        if not await parser.connect():
            return

        # Пример использования - укажите ваш чат
        chat = config.target_chat

        if not chat:
            print("Укажите TARGET_CHAT в .env файле или config.py")
            # Вывод списка диалогов для выбора
            print("\nВаши диалоги:")
            dialogs = await parser.client.get_dialogs(limit=20)
            for dialog in dialogs:
                print(f"  - {dialog.name}: {dialog.entity.id}")
            return

        # Получаем информацию о чате
        chat_info = await parser.get_chat_info(chat)
        print(f"\nИнформация о чате: {chat_info}")

        # Информация о фильтрах
        if config.start_date or config.end_date:
            print(f"Фильтр по датам: {config.start_date or 'начало'} - {config.end_date or 'сейчас'}")

        # Парсим сообщения
        messages = await parser.parse_messages(
            chat_identifier=chat,
            limit=config.message_limit,
            start_date=config.start_date,
            end_date=config.end_date,
        )

        # Сохраняем результаты
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        parser.save_to_json(messages, f"messages_{timestamp}.json")
        parser.save_to_csv(messages, f"messages_{timestamp}.csv")

        # Опционально: скачать медиа
        if config.download_media:
            await parser.download_media(messages, chat)

    finally:
        await parser.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
