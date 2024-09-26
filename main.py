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
    "Словарь",
    "Добавить тему",
    "Добавить слова",
    "Выбрать тему"
]

class TranslationStates(StatesGroup):
    ENG_RU = State()
    RU_ENG = State()

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
async def update_learned_words_count(user_id: int) -> int:
    from functions.profile import update_learned_words_count
    await update_learned_words_count(user_id)


# Функция для обновления количества созданных тем
async def update_learned_topics_count(user_id: int) -> None:
    from functions.profile import update_learned_topics_count
    await update_learned_topics_count(user_id)


# Функция для поиска тем пользователя
async def search_user_topics(user_id: int, query: str) -> list:
    from functions.add_words import search_user_topics
    await search_user_topics(user_id, query)


# Обработка нажатия на кнопку "Начать обучение!"
@dp.callback_query(lambda c: c.data == 'start_learning')
async def process_start_learning(callback_query: types.CallbackQuery) -> None:
    from functions.start_command import process_start_learning
    await process_start_learning(callback_query)


# Обработка внутренностей "Словарь"
@dp.message(F.text == "Словарь")
async def learning(message: types.Message) -> None:
    from functions.learning import learning
    await learning(message)

# Проверяет, существует ли тема с заданным названием
async def is_topic_exists(author_id: int, content: str) -> bool:
    from functions.add_topic import is_topic_exists
    await is_topic_exists(author_id, content)


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

@dp.inline_query(F.query.startswith("поиск темы для добавления слов: "))
async def inline_query_handler(inline_query: types.InlineQuery) -> None:
    from functions.add_words import inline_query_handler
    await inline_query_handler(inline_query)

# Обработка выбора темы из inline клавиатуры
@dp.message(lambda message: message.text.startswith("Вы выбрали тему:"))
async def process_topic_selection(message: types.Message, state: FSMContext) -> None:
    from functions.add_words import process_topic_selection
    await process_topic_selection(message, state)

# Обработка нажатия на инлайн-кнопку "Добавить слово"
@dp.callback_query(lambda c: c.data.startswith("add_words:"))
async def add_words_callback(callback_query: types.CallbackQuery, state: FSMContext):
    from functions.add_words import add_words_callback
    await add_words_callback(callback_query, state)

# Обработка текста для добавления слова
@dp.message(Form.waiting_for_word)
async def handle_word_translation(message: types.Message, state: FSMContext) -> None:
    from functions.add_words import handle_word_input
    await handle_word_input(message, state)

# Обработка текста для добавления перевода
@dp.message(Form.waiting_for_translation)
async def process_translation(message: types.Message, state: FSMContext) -> None:
    from functions.add_words import process_translation
    await process_translation(message, state)

# Обработка нажатия на инлайн-кнопку "Удалить тему"
@dp.callback_query(lambda c: c.data.startswith("delete_topic:"))
async def delete_topic_callback(callback_query: types.CallbackQuery):
    from functions.add_words import delete_topic_callback
    await delete_topic_callback(callback_query)

# Обработка подтверждения удаления темы
@dp.callback_query(lambda c: c.data.startswith("confirm_delete:"))
async def confirm_delete_topic(callback_query: types.CallbackQuery):
    from functions.add_words import confirm_delete_topic
    await confirm_delete_topic(callback_query)

# Обработка отмены удаления темы
@dp.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete_topic(callback_query: types.CallbackQuery):
    from functions.add_words import cancel_delete_topic
    await cancel_delete_topic(callback_query)

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


# Обработка текстового сообщения "Повторение слов"
@dp.message(F.text == "Повторение слов")
async def add_words_prompt(message: types.Message, state: FSMContext) -> None:
    from functions.repeat_words import repeat_words
    await repeat_words(message, state)

@dp.inline_query(F.query.startswith("поиск тем для повторения: "))
async def inline_query_handler_repeat(inline_query: types.InlineQuery) -> None:
    from functions.repeat_words import inline_query_handler_repeat
    await inline_query_handler_repeat(inline_query)

# Обработка выбранной темы сразу после инлайн-запроса
@dp.message(lambda message: message.text.startswith("Для повторения была выбрана тема:"))
async def process_topic_selection_repeat(message: types.Message, state: FSMContext) -> None:
    from functions.repeat_words import process_topic_selection_repeat
    await process_topic_selection_repeat(message, state)



# Состояние для хранения текущего слова
@dp.callback_query(lambda c: c.data.startswith("eng_ru:"))
async def start_eng_ru_translation(callback_query: types.CallbackQuery, state: FSMContext):
    from functions.repeat_words import start_eng_ru_translation
    await start_eng_ru_translation(callback_query, state)

# Обработка текстового сообщения "Прекратить повтор"
@dp.message(F.text == "Прекратить повтор")
async def stop_translation(message: types.Message, state: FSMContext):
    from functions.repeat_words import stop_translation
    await stop_translation(message, state)


async def ask_for_ru_translation(message: types.Message, user_id: int, topic_id: int, state: FSMContext):
    from functions.repeat_words import ask_for_ru_translation
    await ask_for_ru_translation(message, user_id, topic_id, state)

# Обработка текстового сообщения перевода
@dp.message(lambda message: message.text.strip() != "Прекратить повтор", F.state == TranslationStates.ENG_RU)
async def check_eng_ru_translation(message: types.Message, state: FSMContext):
    from functions.repeat_words import check_eng_ru_translation
    await check_eng_ru_translation(message, state)

@dp.callback_query(lambda c: c.data.startswith("ru_eng:"))
async def start_ru_eng_translation(callback_query: types.CallbackQuery, state: FSMContext):
    from functions.repeat_words import start_ru_eng_translation
    await start_ru_eng_translation(callback_query, state)

async def ask_for_eng_translation1(message: types.Message, user_id: int, topic_id: int, state: FSMContext):
    from functions.repeat_words import ask_for_eng_translation
    await ask_for_eng_translation(message, user_id, topic_id, state)

@dp.message(lambda message: message.text.strip() != "Прекратить повтор" and F.state == TranslationStates.RU_ENG)
async def check_ru_eng_translation(message: types.Message, state: FSMContext):
    from functions.repeat_words import check_ru_eng_translation
    await check_ru_eng_translation(message, state)

# функция обработки простого текста
@dp.message(F.text)
async def handle_any_text(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state is not None and current_state != TranslationStates.ENG_RU.state and current_state != TranslationStates.RU_ENG.state:  # Проверка на состояние перевода
        await state.clear()  # Сбрасываем состояние
        await message.answer("Текущее действие отменено. Выберите новое действие.")


# Запуск бота
async def main() -> None:
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
