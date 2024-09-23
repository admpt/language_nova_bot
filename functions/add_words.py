import logging
import sqlite3
from sqlite3 import Connection

from aiogram import F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, \
    ReplyKeyboardMarkup
from pyexpat.errors import messages

from main import DB_FILE, update_learned_words_count, Form, is_command
from token_of_bot import API_TOKEN

TOKEN = API_TOKEN
from main import dp
bot = Bot(token=TOKEN)


# Функция для поиска тем пользователя
async def search_user_topics(user_id: int, query: str) -> list:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()

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

# Обработка команды "Добавить слова"
@dp.message(F.text == "Добавить слова")
async def add_words_prompt(message: types.Message, state: FSMContext) -> None:
    await state.clear()  # Сбрасываем состояние
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать тему", switch_inline_query_current_chat="")]
    ])
    await message.answer("Выберите тему из предложенных:\nДоделать описание", reply_markup=kb)


@dp.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery) -> None:
    query = inline_query.query.strip()
    user_id = inline_query.from_user.id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Поиск тем по запросу
        cursor.execute("""SELECT id, content
                          FROM topics
                          WHERE (author_id = ? OR visible = 1) AND content LIKE ?""",
                       (user_id, f'%{query}%'))
        results = cursor.fetchall()

        items = [
            InlineQueryResultArticle(
                id=str(item[0]),
                title=item[1],
                input_message_content=InputTextMessageContent(
                    message_text=f"Вы выбрали тему: {item[1]}"
                )
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

    except sqlite3.OperationalError as e:
        logging.error(f"Database error: {e}")
        await bot.answer_inline_query(inline_query.id, results=[])
    finally:
        conn.close()

# Обработка выбранной темы сразу после инлайн-запроса
@dp.message(lambda message: message.text.startswith("Вы выбрали тему:"))
async def process_topic_selection(message: types.Message) -> None:
    topic_name = message.text.split(": ", 1)[-1]

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Получаем ID темы по имени
        cursor.execute("SELECT id FROM topics WHERE content = ?", (topic_name,))
        topic = cursor.fetchone()

        if topic:
            topic_id = topic[0]
            cursor.execute("SELECT COUNT(*) FROM user_dictionary WHERE topic_id = ?", (topic_id,))
            word_count = cursor.fetchone()[0]

            message_text = f"Название темы*{topic_name}*\nКоличество слов: {word_count}" if word_count > 0 else f"*{topic_name}*\nКоличество слов: 0"

            # Дальнейшие действия
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Добавить слова", callback_data=f"add_words:{topic_id}"),
                 InlineKeyboardButton(text="Удалить тему", callback_data=f"delete_topic:{topic_id}")]
            ])
            await message.answer(message_text, parse_mode='Markdown', reply_markup=kb)
        else:
            await message.answer("Тема не найдена.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Произошла ошибка при получении данных.")
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



@dp.callback_query(lambda c: c.data.startswith("add_words:"))
async def add_words_callback(callback_query: types.CallbackQuery, state: FSMContext):
    topic_id = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    logging.info("Выбор темы для добавления слов")
    await state.update_data(selected_topic_id=topic_id)
    await callback_query.message.answer("Введите слово на английском:")
    await state.set_state(Form.waiting_for_word)

# Обработка текста для добавления слова
@dp.message(Form.waiting_for_word)
async def handle_word_input(message: types.Message, state: FSMContext) -> None:
    word = message.text.strip()
    logging.info(f"Получено слово: {word}")

    if is_command(word):
        await message.answer("Вы не можете использовать названия команд в качестве аргументов.")
        return

    await state.update_data(word_to_add=word)
    await message.answer("Введите перевод слова:")
    await state.set_state(Form.waiting_for_translation)

# Функция для добавления слова в выбранную тему
async def add_word_to_user_topic(user_id: int, topic_id: int, word: str, translation: str) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO user_dictionary (user_id, topic_id, word, translation)
                          VALUES (?, ?, ?, ?)""", (user_id, topic_id, word, translation))
        await update_learned_words_count(user_id)  # Обновляем количество изученных слов
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()

# Обработка текста для добавления перевода
@dp.message(Form.waiting_for_translation)
async def process_translation(message: types.Message, state: FSMContext) -> None:
    translation = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    word = data.get('word_to_add')
    topic_id = data.get('selected_topic_id')

    logging.info(f"Получен перевод: {translation} для слова: {word} в теме с ID: {topic_id}")

    if not topic_id:
        await message.answer("Ошибка: не выбрана тема для добавления слова.")
        return

    if is_command(translation):
        await message.answer("Вы не можете использовать названия команд в качестве аргументов.")
        return

    await add_word_to_user_topic(user_id, topic_id, word, translation)
    await state.clear()  # Очищаем состояние после добавления

    await message.answer(f"Вы успешно добавили слово '{word}' с переводом '{translation}' в тему с ID '{topic_id}'!")