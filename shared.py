import logging
import sqlite3
from sqlite3 import Connection

from aiogram import Dispatcher, Bot
from aiogram.fsm.state import StatesGroup, State

from token_of_bot import API_TOKEN

TOKEN = API_TOKEN
DB_FILE = 'database.db'

# Создание экземпляров
bot = Bot(token=TOKEN)
dp = Dispatcher()

class DeleteStates(StatesGroup):
    waiting_for_deletion = State()

class TranslationStates(StatesGroup):
    ENG_RU = State()
    RU_ENG = State()
    repeat_irregular_verbs = State()
    ask_past_simple = State()
    ask_past_participle = State()
    ask_translation = State()
    check_translation = State()
# Состояния пользователя
class Form(StatesGroup):
    waiting_for_topic_name = State()
    waiting_for_word = State()
    waiting_for_translation = State()


# Функция для создания соединения с базой данных
def create_connection(db_file: str) -> Connection:
    try:
        conn = sqlite3.connect(db_file)
        logging.info("Connection to database established.")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        raise


# Функция для проверки на наличие команд
def is_command(text: str) -> bool:
    return text.startswith('/')

# Функция для обновления количества изученных слов
async def update_learned_words_count(user_id: int) -> int:
    from functions.profile import update_learned_words_count
    await update_learned_words_count(user_id)

# Функция для обновления количества созданных тем
async def update_learned_topics_count(user_id: int) -> None:
    from functions.profile import update_learned_topics_count
    await update_learned_topics_count(user_id)