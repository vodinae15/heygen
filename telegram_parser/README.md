# Telegram Chat Parser

Парсер для извлечения всех сообщений из Telegram чатов, каналов и групп.

## Возможности

- Парсинг всех сообщений из чата/канала/группы
- Сохранение в JSON и CSV форматы
- Извлечение информации о медиа (фото, видео, документы, стикеры)
- Скачивание медиа файлов
- Информация об отправителе, реакциях, пересылках
- Поиск по сообщениям
- Фильтрация по дате и ID

## Установка

1. Клонируйте репозиторий и перейдите в директорию:
```bash
cd telegram_parser
```

2. Создайте виртуальное окружение (рекомендуется):
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

## Настройка

### 1. Получите Telegram API credentials

1. Перейдите на https://my.telegram.org/apps
2. Войдите с вашим номером телефона
3. Создайте новое приложение
4. Скопируйте `api_id` и `api_hash`

### 2. Создайте файл конфигурации

```bash
cp .env.example .env
```

Отредактируйте `.env` файл:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+79001234567
TARGET_CHAT=@channel_username
MESSAGE_LIMIT=1000
DOWNLOAD_MEDIA=false
```

## Использование

### Базовый запуск

```bash
python parser.py
```

При первом запуске потребуется ввести код подтверждения из Telegram.

### Программное использование

```python
import asyncio
from parser import TelegramChatParser
from config import Config

async def main():
    config = Config()
    parser = TelegramChatParser(config)

    await parser.connect()

    # Парсинг всех сообщений
    messages = await parser.parse_messages("@channel_username")

    # Сохранение результатов
    parser.save_to_json(messages, "messages.json")
    parser.save_to_csv(messages, "messages.csv")

    await parser.disconnect()

asyncio.run(main())
```

### Параметры парсинга

```python
messages = await parser.parse_messages(
    chat_identifier="@channel",  # username, ID, или ссылка
    limit=1000,                  # максимум сообщений (None = все)
    offset_date=datetime(2024, 1, 1),  # сообщения до этой даты
    min_id=100,                  # минимальный ID сообщения
    max_id=5000,                 # максимальный ID сообщения
    search="ключевое слово",     # поиск по тексту
)
```

## Структура выходных данных

### JSON формат

```json
{
  "id": 12345,
  "date": "2024-01-15T10:30:00+00:00",
  "text": "Текст сообщения",
  "sender_id": 123456789,
  "sender_name": "Имя Фамилия",
  "sender_username": "username",
  "reply_to_msg_id": 12344,
  "forward_from_id": null,
  "views": 1500,
  "forwards": 50,
  "reactions": [
    {"emoji": "👍", "count": 100},
    {"emoji": "❤️", "count": 50}
  ],
  "media": {
    "type": "photo",
    "id": 987654321
  },
  "edit_date": null,
  "is_pinned": false
}
```

## Типы чатов

Парсер поддерживает:

- **Публичные каналы**: `@channel_username`
- **Приватные каналы/группы**: ID с префиксом `-100`, например `-1001234567890`
- **Личные чаты**: username или ID пользователя
- **Ссылки**: `https://t.me/channel_username`

## Ограничения

- Требуется доступ к чату (подписка на канал или членство в группе)
- Telegram API имеет лимиты на количество запросов
- Для приватных чатов нужно быть участником

## Структура проекта

```
telegram_parser/
├── parser.py          # Основной модуль парсера
├── config.py          # Конфигурация
├── .env.example       # Пример файла конфигурации
├── requirements.txt   # Зависимости
└── output/            # Результаты парсинга
    ├── messages_*.json
    ├── messages_*.csv
    └── media/         # Скачанные медиа файлы
```

## Лицензия

MIT
