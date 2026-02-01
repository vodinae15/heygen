"""
Конфигурация для Telegram Chat Parser
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()


class Config:
    """Конфигурация парсера"""

    def __init__(self):
        # Telegram API credentials
        # Получить на https://my.telegram.org/apps
        self.api_id: int = int(os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash: str = os.getenv("TELEGRAM_API_HASH", "")

        # Номер телефона для авторизации
        self.phone_number: str = os.getenv("TELEGRAM_PHONE", "")

        # Имя сессии (файл сессии будет сохранен локально)
        self.session_name: str = os.getenv("SESSION_NAME", "telegram_parser_session")

        # Целевой чат для парсинга
        # Может быть: username (@channel), ID (-100xxx), или ссылка (t.me/channel)
        self.target_chat: str = os.getenv("TARGET_CHAT", "")

        # Лимит сообщений (None = все сообщения)
        limit_str = os.getenv("MESSAGE_LIMIT", "")
        self.message_limit: int | None = int(limit_str) if limit_str else None

        # Директория для сохранения результатов
        self.output_dir: str = os.getenv("OUTPUT_DIR", str(Path(__file__).parent / "output"))

        # Скачивать медиа файлы
        self.download_media: bool = os.getenv("DOWNLOAD_MEDIA", "false").lower() == "true"

    def validate(self) -> bool:
        """Проверка обязательных параметров"""
        if not self.api_id or self.api_id == 0:
            print("Ошибка: TELEGRAM_API_ID не указан")
            return False

        if not self.api_hash:
            print("Ошибка: TELEGRAM_API_HASH не указан")
            return False

        if not self.phone_number:
            print("Ошибка: TELEGRAM_PHONE не указан")
            return False

        return True

    def __repr__(self) -> str:
        return (
            f"Config(\n"
            f"  api_id={self.api_id},\n"
            f"  phone={self.phone_number[:4]}****,\n"
            f"  target_chat={self.target_chat},\n"
            f"  message_limit={self.message_limit},\n"
            f"  output_dir={self.output_dir},\n"
            f"  download_media={self.download_media}\n"
            f")"
        )
