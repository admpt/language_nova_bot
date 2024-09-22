import logging
import sqlite3
from sqlite3 import Connection

from aiogram import F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, \
    ReplyKeyboardMarkup

from main import DB_FILE, update_learned_words_count, Form, is_command
from token_of_bot import API_TOKEN

TOKEN = API_TOKEN
from main import dp
bot = Bot(token=TOKEN)

# Обработка команды "Добавить слова"
@dp.message(F.text == "Добавить слова")
async def add_words_prompt(message: types.Message, state: FSMContext) -> None:
    await state.clear()  # Сбрасываем состояние
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать тему", switch_inline_query_current_chat="")]
    ])
    await message.answer("Выберите тему из предложенных:", reply_markup=kb)

# @dp.inline_query()
# async def inline_query_handler(inline_query: types.InlineQuery) -> None:
#     query = inline_query.query.strip()
#     user_id = inline_query.from_user.id
#
#     # Подключение к базе данных
#     conn = sqlite3.connect(DB_FILE)
#     cursor = conn.cursor()
#
#     try:
#         # Поиск тем по запросу, используя столбец `content`
#         cursor.execute("""SELECT id, content
#                           FROM topics
#                           WHERE (author_id = ? OR visible = 1) AND content LIKE ?
#                        """, (user_id, f'%{query}%'))
#         results = cursor.fetchall()
#     except sqlite3.OperationalError as e:
#         logging.error(f"Database error: {e}")
#         results = []
#     finally:
#         conn.close()
#
#     # Формирование результатов
#     items = [
#         InlineQueryResultArticle(
#             id=str(item[0]),
#             title=item[1],
#             input_message_content=InputTextMessageContent(message_text=f"Вы выбрали тему: {item[1]}")
#         )
#         for item in results
#     ]
#     if not items:
#         items = [
#             InlineQueryResultArticle(
#                 id="no_results",
#                 title="Нет доступных тем",
#                 input_message_content=InputTextMessageContent(message_text="Не найдено тем по вашему запросу.")
#             )
#         ]
#     # Отправка результатов
#     await bot.answer_inline_query(inline_query.id, results=items)
@dp.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery) -> None:
    query = inline_query.query.strip()
    user_id = inline_query.from_user.id
    # Подключение к базе данных
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Поиск тем по запросу
        cursor.execute("""SELECT id, content
                          FROM topics
                          WHERE (author_id = ? OR visible = 1) AND content LIKE ?
                       """, (user_id, f'%{query}%'))
        results = cursor.fetchall()
        # Формирование результатов
        items = [
            InlineQueryResultArticle(
                id=str(item[0]),
                title=item[1],
                input_message_content=InputTextMessageContent(message_text=f"Вы выбрали тему: {item[1]}")
            )
            for item in results
        ]
        # Если нет тем, добавляем сообщение о пустых темах
        if not items:
            cursor.execute("""SELECT id, content
                              FROM topics
                              WHERE author_id = ? AND content LIKE ?
                           """, (user_id, f'%{query}%'))
            empty_results = cursor.fetchall()
            if empty_results:
                for item in empty_results:
                    items.append(
                        InlineQueryResultArticle(
                            id=str(item[0]),
                            title=item[1],
                            input_message_content=InputTextMessageContent(
                                message_text=f"Вы выбрали тему: {item[1]}\n(в теме пока нет слов)")
                        )
                    )
        # Если все равно нет результатов, сообщаем об этом
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

    except sqlite3.OperationalError as e:
        logging.error(f"Database error: {e}")
        await bot.answer_inline_query(inline_query.id, results=[])
    finally:
        conn.close()


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
async def upsert_user(user_id: int, username_tg: str, full_name: str, balance: int = 0, elite_status: str = 'No',
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

# Функция для добавления слова в выбранную тему
async def add_word_to_user_topic(user_id: int, topic_id: int, word: str, translation: str, state: FSMContext) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO user_dictionary (user_id, topic_id, word, translation)
                          VALUES (?, ?, ?, ?)
                       """, (user_id, topic_id, word, translation))
        await update_learned_words_count(user_id)
        conn.commit()
        await state.clear()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()

# Функция для поиска тем пользователя
async def search_user_topics(user_id: int, query: str) -> list:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()

        # Логируем, что мы ищем темы
        logging.info(f"Searching topics for user {user_id} with query: {query}")

        cursor.execute("""SELECT id, content 
                          FROM topics 
                          WHERE (author_id = ? OR visible = 1) 
                          AND content LIKE ?""", (user_id, f"%{query}%"))

        results = cursor.fetchall()

        # Логируем результаты поиска
        logging.info(f"Found topics: {results}")

        return results
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return []
    finally:
        conn.close()

# Обработка выбора темы из inline клавиатуры
@dp.callback_query(lambda c: c.data.startswith('select_topic_'))
async def process_topic_selection_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    logging.info("Callback handler triggered")
    topic_id = callback_query.data.split("_")[-1]
    await bot.answer_callback_query(callback_query.id)

    # Логируем, что мы получили topic_id
    logging.info(f"Selected topic ID: {topic_id}")

    conn = create_connection(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT content FROM topics WHERE id = ?", (topic_id,))
        topic_content = cursor.fetchone()
        logging.info(f"Fetched topic content: {topic_content}")

        # Получение количества слов
        cursor.execute("SELECT COUNT(*) FROM user_dictionary WHERE topic_id = ?", (topic_id,))
        word_count = cursor.fetchone()[0]
        logging.info(f"Word count for topic ID {topic_id}: {word_count}")

        if topic_content:
            topic_name = topic_content[0]
            message_text = f"*{topic_name}*\nКоличество слов: {word_count}" if word_count > 0 else f"*{topic_name}*\nКоличество слов: 0 (в теме пока нет слов)"

            logging.info("Sending message with topic details")
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