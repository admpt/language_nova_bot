import sqlite3
from sqlite3 import Connection
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, KeyboardButton
import asyncio
import logging
import sys
import functions.start_command
from functions.start_command import *

from token_of_bot import API_TOKEN

TOKEN = API_TOKEN
DB_FILE = 'database.db'
# logging.basicConfig(level=logging.INFO)

# Создание экземпляров
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Список команд
COMMANDS = [
    "/start",
    "/help",
    "Изучение слов",
    "Добавить тему",
    "Добавить слова",
    "Выбрать тему"
]

# Состояния пользователя
class Form(StatesGroup):
    waiting_for_topic_name = State()
    waiting_for_word = State()
    waiting_for_translation = State()

# Функция для проверки на наличие команд
def is_command(text: str) -> bool:
    return text.startswith('/')

# Функция для создания соединения с базой данных
def create_connection(db_file: str) -> Connection:
    try:
        conn = sqlite3.connect(db_file)
        logging.info("Connection to database established.")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        raise

@dp.message(F.text == "Отменить действие")
async def cancel_action(message: types.Message, state: FSMContext) -> None:
    from functions.add_topic import cancel_action
    await cancel_action(message, state)

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

# Функция для обновления количества изученных слов
async def update_learned_words_count(user_id: int) -> None:
    from functions.profile import update_learned_words_count
    await update_learned_words_count(user_id)

# Функция для поиска тем пользователя
async def search_user_topics(user_id: int, query: str) -> list:
    from functions.add_words import search_user_topics
    await search_user_topics(user_id, query)

# Обработка нажатия на кнопку "Начать обучение!"
@dp.callback_query(lambda c: c.data == 'start_learning')
async def process_start_learning(callback_query: types.CallbackQuery) -> None:
    from functions.start_command import process_start_learning
    await process_start_learning(callback_query)

# Обработка внутренностей "Изучение слов"
@dp.message(F.text == "Изучение слов")
async def learning(message: types.Message) -> None:
    from functions.learning import learning
    await learning(message)

# Обработка нажатия на кнопку "Добавить тему"
@dp.message(F.text == "Добавить тему")
async def add_topic_prompt(message: types.Message, state: FSMContext) -> None:
    await state.clear()  # Сбрасываем состояние перед установкой нового
    from functions.add_topic import add_topic_prompt
    await add_topic_prompt(message, state)

# Обработка текста для добавления темы
@dp.message(Form.waiting_for_topic_name)
async def process_add_topic(message: types.Message, state: FSMContext) -> None:
    from functions.add_topic import process_add_topic
    await process_add_topic(message, state)

# Обработка команды "🔙Назад"
@dp.message(F.text == "🔙Назад")
async def go_back(message: types.Message, state: FSMContext) -> None:
    from functions.add_topic import go_back
    await go_back(message, state)

# Обработка команды "Добавить слова"
@dp.message(F.text == "Добавить слова")
async def add_words_prompt(message: types.Message, state: FSMContext) -> None:
    from functions.add_words import add_words_prompt
    await add_words_prompt(message, state)

@dp.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery) -> None:
    from functions.add_words import inline_query_handler
    await inline_query_handler(inline_query)

# Обработка выбора темы из inline клавиатуры
@dp.callback_query(lambda c: c.data.startswith('select_topic_'))
async def process_topic_selection_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    from functions.add_words import process_topic_selection_callback
    await process_start_learning(callback_query, state)

# Обработка текста для добавления слова
@dp.message(F.state == Form.waiting_for_word | F.state == Form.waiting_for_translation)
async def handle_word_translation(message: types.Message, state: FSMContext) -> None:
    from functions.add_words import handle_word_translation
    await handle_word_translation(message, state)

# Обработка текста для добавления перевода
@dp.message(F.state.in_(Form.waiting_for_translation))
async def process_translation(message: types.Message, state: FSMContext) -> None:
    from functions.add_words import process_translation
    await process_translation(message, state)

# Обработка команды /help
@dp.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer("Это бот для изучения английского языка. Используйте команды и кнопки для добавления тем и слов.")

# Обработка команды /start
@dp.message(Command("start"))
async def handle_start(message: types.Message, state: FSMContext):
    await process_start_command(message, state, upsert_user)  # Вызываем обработчик

# Обработка кнопки "Топ пользователей"
@dp.callback_query(F.data == "top_leaders")
async def handle_top_leaders(callback_query: types.CallbackQuery, state: FSMContext):
    from functions.profile import top_users  # Отложенный импорт
    await top_users(callback_query, state)

# Обработка текстового сообщения "Профиль"
@dp.message(F.text == "Профиль")
async def handle_profile(message: types.Message, state: FSMContext):
    from functions.profile import check_profile  # Отложенный импорт
    await check_profile(message, state)  # Вызываем обработчик

# функция обработки простого текста
@dp.message(F.text)
async def handle_any_text(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is not None:  # Если состояние активно
        await state.clear()  # Сбрасываем состояние
        await message.answer("Текущее действие отменено. Выберите новое действие.")

# Запуск бота
async def main() -> None:
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
