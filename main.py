import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import asyncio
import sys

from aiogram.fsm.context import FSMContext
import datetime
from functions.add_topic import add_topic_prompt, add_topic_router
from functions.add_words import add_words_router
from functions.grammar import grammar_router
from functions.learning import learning_router
from functions.profile import profile_router
from functions.repeat_words import repeat_words_router
from functions.start_command import process_start_command, start_router
from shared import Form, TranslationStates, TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Список команд
COMMANDS = [
    "/start",
    "/help",
    "Словарь",
    "Добавить тему",
    "Добавить слова",
    "Выбрать тему",
    "Грамматика",
    "Прекратить повтор",
    "Отменить действие"
]
dp.include_router(profile_router)
dp.include_router(learning_router)
dp.include_router(add_topic_router)
dp.include_router(add_words_router)
dp.include_router(repeat_words_router)
dp.include_router(grammar_router)
dp.include_router(start_router)

# Функция для добавления или обновления пользователя в базе данных
async def upsert_user(user_id: int, username_tg: str, full_name: str, balance: int = 0, elite_status: str = 'No',
                learned_words_count: int = 0) -> None:
    from functions.start_command import upsert_user
    await upsert_user(user_id, username_tg, full_name, balance, elite_status, learned_words_count)


# Функция для добавления темы в базу данных (с привязкой к пользователю)
async def add_user_topic(author_id: int, content: str, visible: int) -> None:
    from functions.add_topic import add_user_topic
    await add_user_topic(author_id, content, visible)


# Функция для добавления слова в выбранную тему
async def add_word_to_user_topic(user_id: int, topic_id: int, word: str, translation: str, state: FSMContext) -> None:
    from functions.add_topic import add_word_to_user_topic
    await add_word_to_user_topic(user_id, topic_id, word, translation, state)


# Функция для поиска тем пользователя
async def search_user_topics(user_id: int, query: str) -> list:
    from functions.add_words import search_user_topics
    await search_user_topics(user_id, query)

# Проверяет, существует ли тема с заданным названием
async def is_topic_exists(author_id: int, content: str) -> bool:
    from functions.add_topic import is_topic_exists
    await is_topic_exists(author_id, content)

# Запуск бота
async def main() -> None:
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
