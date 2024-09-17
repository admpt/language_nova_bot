import sqlite3
from sqlite3 import Connection
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
import asyncio
import logging
import sys

from bot_token import API_TOKEN

TOKEN = API_TOKEN
DB_FILE = 'database.db'

# Создание экземпляров
bot = Bot(token=TOKEN)
dp = Dispatcher()

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
def add_user_topic(user_id: int, topic_name: str) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO topics (user_id, name)
                          VALUES (?, ?)
                          ON CONFLICT(user_id, name) DO NOTHING
                       """, (user_id, topic_name))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()

# Функция для добавления слова в выбранную тему
def add_word_to_user_topic(user_id: int, topic_name: str, word: str, translation: str) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO user_dictionary (user_id, topic_name, word, translation)
                          VALUES (?, ?, ?, ?)
                       """, (user_id, topic_name, word, translation))

        # Обновляем количество изученных слов
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
        cursor.execute("""SELECT COUNT(*) FROM user_dictionary WHERE user_id = ?
                       """, (user_id,))
        learned_words_count = cursor.fetchone()[0]
        cursor.execute("""UPDATE users SET learned_words_count = ? WHERE user_id = ?
                       """, (learned_words_count, user_id))
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
        cursor.execute("""SELECT name FROM topics WHERE user_id = ? AND name LIKE ?
                       """, (user_id, f"{query}%"))
        return [row[0] for row in cursor.fetchall()]
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

    # Отправляем сообщение с кнопками "Изучение слов" и "Профиль"
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

    # Отправляем сообщение с кнопками "Добавить тему" и "Добавить слова"
    kb = [
        [types.KeyboardButton(text="Добавить тему")],
        [types.KeyboardButton(text="Добавить слова")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer("Что вы хотите сделать дальше?", reply_markup=keyboard)

# Обработка нажатия на кнопку "Добавить тему"
@dp.message(F.text == "Добавить тему")
async def add_topic_prompt(message: types.Message) -> None:
    await message.answer("Введите название темы:")

# Обработка текста для добавления темы
@dp.message(lambda m: m.text and m.text != "Добавить тему" and m.text != "Добавить слова" and m.text != "Профиль")
async def process_add_topic(message: types.Message) -> None:
    user_id = message.from_user.id
    topic_name = message.text
    add_user_topic(user_id, topic_name)

    kb = [
        [types.KeyboardButton(text="Добавить тему")],
        [types.KeyboardButton(text="Добавить слова")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer("Вы успешно добавили тему!", reply_markup=keyboard)

# Обработка нажатия на кнопку "Добавить слова"
@dp.message(F.text == "Добавить слова")
async def add_words_prompt(message: types.Message) -> None:
    kb = [
        [types.KeyboardButton(text="Выбрать тему")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer(
        "Введите название темы для добавления слов:",
        reply_markup=keyboard
    )

# Обработка нажатия на кнопку "Выбрать тему"
@dp.message(F.text == "Выбрать тему")
async def choose_topic(message: types.Message) -> None:
    user_id = message.from_user.id
    topics = search_user_topics(user_id, '')  # Получаем все темы пользователя

    if topics:
        kb = [
            [types.InlineKeyboardButton(text=topic, callback_data=f"select_topic_{topic}") for topic in topics]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        await message.answer("Выберите тему из предложенных:", reply_markup=keyboard)
    else:
        await message.answer("У вас нет доступных тем. Пожалуйста, создайте хотя бы одну тему.")

# Обработка выбора темы из inline клавиатуры
@dp.callback_query(lambda c: c.data.startswith('select_topic_'))
async def process_topic_selection_callback(callback_query: types.CallbackQuery) -> None:
    topic_name = callback_query.data[len('select_topic_'):]
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, f"Вы выбрали тему: {topic_name}. Введите слово на английском:")

    # Сохранение выбранной темы в пользовательском контексте
    dp.user_data[callback_query.from_user.id] = {'selected_topic': topic_name}

# Обработка текста для добавления слова
@dp.message(lambda m: m.text and m.text != "Добавить тему" and m.text != "Добавить слова" and m.text != "Выбрать тему")
async def process_word(message: types.Message) -> None:
    user_id = message.from_user.id
    if 'selected_topic' in dp.user_data.get(user_id, {}):
        topic_name = dp.user_data[user_id]['selected_topic']
        word = message.text
        # Запрос перевода
        await bot.send_message(user_id, f"Введите перевод для слова '{word}':")
        dp.user_data[user_id]['word_to_add'] = word
        dp.user_data[user_id]['topic_to_add'] = topic_name
    else:
        await message.answer("Сначала выберите тему для добавления слова.")

# Обработка перевода слова
@dp.message(lambda m: m.text and m.text != "Добавить тему" and m.text != "Добавить слова" and m.text != "Выбрать тему" and m.text != "Введите слово на английском:")
async def process_translation(message: types.Message) -> None:
    user_id = message.from_user.id
    if 'word_to_add' in dp.user_data.get(user_id, {}):
        word = dp.user_data[user_id]['word_to_add']
        translation = message.text
        topic_name = dp.user_data[user_id]['topic_to_add']
        add_word_to_user_topic(user_id, topic_name, word, translation)

        # Очистка контекста пользователя
        dp.user_data[user_id].pop('word_to_add', None)
        dp.user_data[user_id].pop('topic_to_add', None)

        kb = [
            [types.KeyboardButton(text="Добавить тему")],
            [types.KeyboardButton(text="Добавить слова")]
        ]
        keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

        await message.answer(f"Вы успешно добавили слово '{word}' в тему '{topic_name}'!", reply_markup=keyboard)

# Обработка команды /help
@dp.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer("Это бот для изучения английского языка. Используйте команды и кнопки для добавления тем и слов.")

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Запуск бота
async def main() -> None:
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
