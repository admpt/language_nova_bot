import sqlite3
from sqlite3 import Connection
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
import asyncio
import logging
import sys

from bot_token import API_TOKEN

TOKEN = API_TOKEN
DB_FILE = 'database.db'

# Создание экземпляров
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Состояния пользователя
class Form(StatesGroup):
    waiting_for_topic_name = State()
    waiting_for_word = State()
    waiting_for_translation = State()

# Функция для создания соединения с базой данных
def create_connection(db_file: str) -> Connection:
    return sqlite3.connect(db_file)

# Функция для добавления или обновления пользователя в базе данных
def upsert_user(user_id: int, username_tg: str, full_name: str, balance: int = 0, elite_status: str = 'No',
                learned_words_count: int = 0) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO users (user_id, username_tg, full_name, balance, elite_status, learned_words_count)
                          VALUES (?, ?, ?, ?, ?, ?)
                          ON CONFLICT(user_id) DO UPDATE SET
                              username_tg = excluded.username_tg,
                              full_name = excluded.full_name,
                              balance = excluded.balance,
                              elite_status = excluded.elite_status,
                              learned_words_count = excluded.learned_words_count
                       """, (user_id, username_tg, full_name, balance, elite_status, learned_words_count))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()

# Функция для добавления темы в базу данных (с привязкой к пользователю)
def add_user_topic(author_id: int, content: str, visible: int) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO topics (author_id, content, visible)
                          VALUES (?, ?, ?)
                          ON CONFLICT(id) DO NOTHING
                       """, (author_id, content, visible))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()

# Функция для добавления слова в выбранную тему
def add_word_to_user_topic(user_id: int, topic_id: int, word: str, translation: str) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO user_dictionary (user_id, topic_id, word, translation)
                          VALUES (?, ?, ?, ?)
                       """, (user_id, topic_id, word, translation))
        update_learned_words_count(user_id)
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()

# Функция для обновления количества изученных слов
def update_learned_words_count(user_id: int) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT COUNT(*) FROM user_dictionary WHERE user_id = ?""", (user_id,))
        learned_words_count = cursor.fetchone()[0]
        cursor.execute("""UPDATE users SET learned_words_count = ? WHERE user_id = ?""", (learned_words_count, user_id))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()

# Функция для поиска тем пользователя
def search_user_topics(user_id: int, query: str) -> list:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT id, content 
                          FROM topics 
                          WHERE (author_id = ? OR visible = 1) 
                          AND content LIKE ?""", (user_id, f"%{query}%"))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return []
    finally:
        conn.close()

# Обработка команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    logging.info(f"Received /start command from {message.from_user.id}")

    button = InlineKeyboardButton(text="Начать обучение!", callback_data="start_learning")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await message.answer("Добро пожаловать! Нажмите кнопку ниже, чтобы начать изучение:", reply_markup=keyboard)

    try:
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name

        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
        elif first_name:
            full_name = first_name
        elif last_name:
            full_name = last_name
        else:
            full_name = ""

        upsert_user(message.from_user.id, message.from_user.username or '', full_name)
        logging.info(f"User data updated for {message.from_user.id}")
    except Exception as e:
        logging.error(f"Error while updating user data: {e}")

# Обработка нажатия на кнопку "Начать обучение!"
@dp.callback_query(lambda c: c.data == 'start_learning')
async def process_start_learning(callback_query: types.CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    await bot.answer_callback_query(callback_query.id)

    kb = [
        [types.KeyboardButton(text="Изучение слов")],
        [types.KeyboardButton(text="Профиль")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await bot.send_message(user_id, "Вы начали изучение! Что вы хотите сделать?", reply_markup=keyboard)

# Обработка внутренностей "Изучение слов"
@dp.message(F.text == "Изучение слов")
async def learning(message: types.Message) -> None:
    user_id = message.from_user.id

    kb = [
        [types.KeyboardButton(text="Добавить тему")],
        [types.KeyboardButton(text="Добавить слова")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer("Что вы хотите сделать дальше?", reply_markup=keyboard)


# Обработка нажатия на кнопку "Добавить тему"
@dp.message(F.text == "Добавить тему")
async def add_topic_prompt(message: types.Message, state: FSMContext) -> None:
    await message.answer("Введите название темы:")
    await state.set_state(Form.waiting_for_topic_name.state)  # Исправление здесь

# Обработка текста для добавления темы
@dp.message(State(Form.waiting_for_topic_name))
async def process_add_topic(message: types.Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    topic_name = message.text
    add_user_topic(user_id, topic_name, visible=0)  # Видимость по умолчанию - 0 (только автор)

    kb = [
        [types.KeyboardButton(text="Добавить тему")],
        [types.KeyboardButton(text="Добавить слова")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer("Вы успешно добавили тему!", reply_markup=keyboard)
    await state.clear()


# Обработка команды "Добавить слова"
@dp.message(F.text == "Добавить слова")
async def add_words_prompt(message: types.Message) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать тему", switch_inline_query_current_chat="")]
    ])
    await message.answer("Выберите тему из предложенных:", reply_markup=kb)

@dp.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery) -> None:
    query = inline_query.query.strip()
    user_id = inline_query.from_user.id

    # Подключение к базе данных
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Поиск тем по запросу, используя столбец `content`
        cursor.execute("""
            SELECT id, content
            FROM topics
            WHERE (author_id = ? OR visible = 1) AND content LIKE ? 
        """, (user_id, f'%{query}%'))
        results = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        results = []
    finally:
        conn.close()

    # Формирование результатов
    items = [
        InlineQueryResultArticle(
            id=str(item[0]),
            title=item[1],
            input_message_content=InputTextMessageContent(message_text=f"Вы выбрали тему: {item[1]}")
        )
        for item in results
    ]

    # Отправка результатов
    await bot.answer_inline_query(inline_query.id, results=items)

# Обработка нажатия на кнопку "Выбрать тему"
@dp.message(F.text == "Выбрать тему")
async def choose_topic(message: types.Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    topics = search_user_topics(user_id, '')  # Получаем все темы пользователя

    logging.info(f"Found topics for user {user_id}: {topics}")

    if topics:
        kb = [[types.InlineKeyboardButton(text=content, callback_data=f"select_topic_{id_}") for id_, content in topics]]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        await message.answer("Выберите тему из предложенных:", reply_markup=keyboard)
    else:
        await message.answer("У вас нет доступных тем. Пожалуйста, создайте хотя бы одну тему.")

# Обработка выбора темы из inline клавиатуры
@dp.callback_query(lambda c: c.data.startswith('select_topic_'))
async def process_topic_selection_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    topic_id = int(callback_query.data[len('select_topic_'):])
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, f"Вы выбрали тему с ID: {topic_id}. Введите слово на английском:")

    # Сохранение выбранной темы в пользовательском контексте
    await state.update_data(selected_topic_id=topic_id)
    await state.set_state(Form.waiting_for_word.state)  # Исправление здесь

# Обработка текста для добавления слова
@dp.message(State(Form.waiting_for_word))
async def process_word(message: types.Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    word = message.text

    # Сохранение введенного слова и ожидание перевода
    await state.update_data(word_to_add=word)
    await message.answer("Введите перевод слова:")
    await state.set_state(Form.waiting_for_translation.state)  # Исправление здесь

# Обработка текста для добавления перевода
@dp.message(State(Form.waiting_for_translation))
async def process_translation(message: types.Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    translation = message.text
    data = await state.get_data()
    word = data.get('word_to_add')
    topic_id = data.get('selected_topic_id')

    add_word_to_user_topic(user_id, topic_id, word, translation)

    # Очистка контекста пользователя
    await state.clear()

    kb = [
        [types.KeyboardButton(text="Добавить тему")],
        [types.KeyboardButton(text="Добавить слова")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer(f"Вы успешно добавили слово '{word}' в тему с ID '{topic_id}'!", reply_markup=keyboard)

# Обработка команды /help
@dp.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer("Это бот для изучения английского языка. Используйте команды и кнопки для добавления тем и слов.")

# Запуск бота
async def main() -> None:
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
