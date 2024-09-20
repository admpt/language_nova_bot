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

from token_of_bot import API_TOKEN

TOKEN = API_TOKEN
DB_FILE = 'database.db'

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

@dp.message(F.text == "Отменить действие")
async def cancel_action(message: types.Message, state: FSMContext) -> None:
    await state.clear()  # Сбрасываем состояние
    # kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb = [
        [(types.KeyboardButton(text="Изучение слов"))],
        [(types.KeyboardButton(text="Профиль"))]
        ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Вы отменили текущее действие. Что вы хотите сделать дальше?", reply_markup=keyboard)

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
        logging.error(f"Ошибка базы данных при добавлении темы: {e}")
    finally:
        conn.close()

# Функция для добавления слова в выбранную тему
async def add_word_to_user_topic(user_id: int, topic_id: int, word: str, translation: str, state: FSMContext) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO user_dictionary (user_id, topic_id, word, translation)
                          VALUES (?, ?, ?, ?)
                       """, (user_id, topic_id, word, translation))
        update_learned_words_count(user_id)
        conn.commit()
        await state.clear()
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
        return learned_words_count
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return 0
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
    await state.clear()  # Сбрасываем состояние перед установкой нового
    kb = [
        [(KeyboardButton(text="Отменить действие"))],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Введите название темы:", reply_markup=keyboard)
    await state.set_state(Form.waiting_for_topic_name.state)


# Обработка текста для добавления темы
@dp.message(Form.waiting_for_topic_name)
async def process_add_topic(message: types.Message, state: FSMContext) -> None:
    author_id = message.from_user.id
    content = message.text

    if is_command(message.text):
        await message.answer("Вы не можете использовать команды в качестве названий тем.")
        return

    if content:
        add_user_topic(author_id, content, 0)
        await message.answer("Вы успешно добавили тему! Что вы хотите сделать дальше?")
        await state.clear()
        logging.info(f"Тема '{content}' добавлена пользователем {author_id}. Состояние сброшено.")
    else:
        await message.answer("Название темы не может быть пустым.")
        logging.warning(f"Пользователь {author_id} ввел пустое название темы.")

# Обработка команды "Добавить слова"
@dp.message(F.text == "Добавить слова")
async def add_words_prompt(message: types.Message, state: FSMContext) -> None:
    await state.clear()  # Сбрасываем состояние
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
        cursor.execute("""SELECT id, content
                          FROM topics
                          WHERE (author_id = ? OR visible = 1) AND content LIKE ? 
                       """, (user_id, f'%{query}%'))
        results = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logging.error(f"Database error: {e}")
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
    if not items:
        items = [
            InlineQueryResultArticle(
                id="no_results",
                title="Нет доступных тем",
                input_message_content=InputTextMessageContent(message_text="Не найдено тем по вашему запросу.")
            )
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
    topic_id = callback_query.data.split("_")[-1]
    await bot.answer_callback_query(callback_query.id)

    logging.info(f"Callback received: {callback_query.data}")
    logging.info(f"Selected topic ID: {topic_id}")

    conn = create_connection(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT content FROM topics WHERE id = ?", (topic_id,))
        topic_content = cursor.fetchone()
        logging.info(f"Fetched topic content: {topic_content}")

        cursor.execute("SELECT COUNT(*) FROM user_dictionary WHERE topic_id = ?", (topic_id,))
        word_count = cursor.fetchone()[0]
        logging.info(f"Word count for topic ID {topic_id}: {word_count}")

        if topic_content:
            topic_name = topic_content[0]
            message_text = f"*{topic_name}*\nКоличество слов: {word_count}"

            await bot.send_message(callback_query.from_user.id, message_text, parse_mode='Markdown')

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Добавить слова", callback_data=f"add_words:{topic_id}"),
                 InlineKeyboardButton(text="Удалить тему", callback_data=f"delete_topic:{topic_id}")]
            ])
            await bot.send_message(callback_query.from_user.id, "Что вы хотите сделать дальше?", reply_markup=kb)
        else:
            await bot.send_message(callback_query.from_user.id, "Тема не найдена.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await bot.send_message(callback_query.from_user.id, "Произошла ошибка при получении данных.")
    finally:
        conn.close()


# Обработка текста для добавления слова
@dp.message(F.state == Form.waiting_for_word | F.state == Form.waiting_for_translation)
async def handle_word_translation(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    word = message.text

    # Проверяем, если сообщение является командой
    if is_command(message.text):
        await message.answer("Вы не можете использовать названия команд в качестве аргументов.")
        return

    # Сохранение введенного слова и ожидание перевода
    await state.update_data(word_to_add=word)
    await message.answer("Введите перевод слова:")
    await state.set_state(Form.waiting_for_translation.state)

# Обработка текста для добавления перевода
@dp.message(F.state.in_(Form.waiting_for_translation))
async def process_translation(message: types.Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    translation = message.text
    data = await state.get_data()
    word = data.get('word_to_add')
    topic_id = data.get('selected_topic_id')

    if not topic_id:
        await message.answer("Ошибка: не выбрана тема для добавления слова.")
        return

    if is_command(translation):
        await message.answer("Вы не можете использовать названия команд в качестве аргументов.")
        return

    await add_word_to_user_topic(user_id, topic_id, word, translation, state)
    await state.clear()

    kb = [
        [types.KeyboardButton(text="Добавить тему")],
        [types.KeyboardButton(text="Добавить слова")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer(f"Вы успешно добавили слово '{word}' в тему с ID '{topic_id}'!", reply_markup=keyboard)

########################################################################################################################

# Обработка команды /help
@dp.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer("Это бот для изучения английского языка. Используйте команды и кнопки для добавления тем и слов.")

########################################################################################################################

# Обработка команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    await state.clear()  # Сбрасываем состояние перед началом
    logging.info(f"Received /start command from {message.from_user.id}")

    button = InlineKeyboardButton(text="Начать обучение!", callback_data="start_learning")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await message.answer("Добро пожаловать! Нажмите кнопку ниже, чтобы начать изучение:", reply_markup=keyboard)

    # Обновляем данные пользователя
    try:
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name

        full_name = f"{first_name} {last_name}" if first_name and last_name else first_name or last_name or ""

        upsert_user(message.from_user.id, message.from_user.username or '', full_name)
        logging.info(f"User data updated for {message.from_user.id}")
    except Exception as e:
        logging.error(f"Error while updating user data: {e}")

########################################################################################################################

async def get_top_users() -> list:
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
                "SELECT user_id, full_name, learned_words_count FROM users ORDER BY learned_words_count DESC LIMIT 15"
        ) as cursor:
            rows = await cursor.fetchall()
            return rows

# @dp.callback_query(F.data == "top_leaders")
# async def top_users(message: types.Message, callback_query: types.CallbackQuery, state: FSMContext) -> None:
#     top_users = await get_top_users()
#
#     if not top_users:
#         await callback_query.message.answer("Топ-15 пользователей отсутствует.")
#         return
#     first_name = message.from_user.first_name
#     last_name = message.from_user.last_name
#     response = "*Top-15 пользователей по изученным словам:*\n\n"
#     for idx, (user_id, full_name, learned_words_count) in enumerate(top_users, start=1):
#         full_name = f"{first_name} {last_name}" if first_name and last_name else first_name or last_name or "Пользователь"
#         user_link = f"[{full_name}](tg://user?id={user_id})"  # Форматируем ссылку
#         response += f"{idx}. {user_link} - {learned_words_count} слов\n"
#
#     response = response.replace(".", "\\.").replace("-", "\\-")
#     (await callback_query.message.answer(response, parse_mode='MarkdownV2')

@dp.callback_query(F.data == "top_leaders")
async def top_users(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    rows = await get_top_users()

    if not rows:
        await callback_query.answer("Топ-15 пользователей отсутствует.")
        return

    response = "*Top-15 пользователей по изученным словам:*\n\n"
    for idx, (user_id, full_name, learned_words_count) in enumerate(rows, start=1):
        user_link = f"[{full_name}](tg://user?id={user_id})"  # Форматируем ссылку
        response += f"{idx}. {user_link} - {learned_words_count} слов\n"

    response = response.replace(".", "\\.").replace("-", "\\-")

    await callback_query.message.answer(response, parse_mode='MarkdownV2')


########################################################################################################################

async def get_user_data(user_id: int):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
                "SELECT full_name, elite_status, learned_words_count FROM users WHERE user_id = ?",
                (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0], row[1], row[2]
            else:
                return None, None, None, 0  # Вернём 0 для изученных слов, если пользователь не найден

# функция для кнопки "Профиль"
@dp.message(F.text == "Профиль")
async def check_profile(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    full_name, elite_status, learned_words_count = await get_user_data(user_id)

    full_name = f"{first_name} {last_name}" if first_name and last_name else first_name or last_name or "Пользователь"

    elite_status_text = " 💎Элитный" if elite_status == "Yes" else " 🆓Free"  # Пример обработки статуса

    button = InlineKeyboardButton(text="Leaders Page", callback_data="top_leaders")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await message.answer(
        f"Имя: [{full_name}](tg://user?id={user_id})\n\nИзученные слова: {learned_words_count}\nСтатус: {elite_status_text}",
        parse_mode='Markdown', reply_markup=keyboard
    )
########################################################################################################################

# функция обработки простого текста
@dp.message(F.text)
async def handle_any_text(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is not None:  # Если состояние активно
        await state.clear()  # Сбрасываем состояние
        await message.answer("Текущее действие отменено. Выберите новое действие.")
########################################################################################################################

# Запуск бота
async def main() -> None:
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
