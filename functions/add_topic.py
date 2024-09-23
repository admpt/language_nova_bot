import logging
import sqlite3

from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from main import dp, Form, is_command, update_learned_words_count, create_connection, DB_FILE, \
    update_learned_topics_count


@dp.message(F.text == "Добавить тему")
async def add_topic_prompt(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    kb = [
        [(KeyboardButton(text="Отменить действие"))],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Введите название темы:", reply_markup=keyboard)
    await state.set_state(Form.waiting_for_topic_name.state)


@dp.message(Form.waiting_for_topic_name)
async def process_add_topic(message: types.Message, state: FSMContext) -> None:
    author_id = message.from_user.id
    content = message.text

    if is_command(message.text):
        await message.answer("Вы не можете использовать команды в качестве названий тем.")
        return

    if content:
        if await is_topic_exists(author_id, content):
            await message.answer("У вас уже есть тема с таким названием.")
            return

        await add_user_topic(author_id, content, 0)

        # Обновляем количество тем после добавления
        await update_learned_topics_count(author_id)

        kb = [
            [KeyboardButton(text="Добавить тему"), KeyboardButton(text="Добавить слова")],
            [KeyboardButton(text="🔙Назад")]
        ]
        keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("Вы успешно добавили тему! Что вы хотите сделать дальше?", reply_markup=keyboard)
        await state.clear()
    else:
        await message.answer("Название темы не может быть пустым.")
        logging.warning(f"Пользователь {author_id} ввел пустое название темы.")


@dp.message(F.text == "🔙Назад")
async def go_back(message: types.Message, state: FSMContext) -> None:
    kb = [
        [types.KeyboardButton(text="Словарь"), types.KeyboardButton(text="Профиль")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Вы вернулись в главное меню.", reply_markup=keyboard)


@dp.message(F.text == "Отменить действие")
async def cancel_action(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    kb = [
        [(types.KeyboardButton(text="Изучение слов"))],
        [(types.KeyboardButton(text="Профиль"))]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Вы отменили текущее действие. Что вы хотите сделать дальше?", reply_markup=keyboard)


async def is_topic_exists(author_id: int, content: str) -> bool:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM topics WHERE author_id = ? AND content = ?", (author_id, content))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return False
    finally:
        conn.close()


async def add_user_topic(author_id: int, content: str, visible: int) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO topics (author_id, content, visible) VALUES (?, ?, ?)",
                       (author_id, content, visible))
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
        await update_learned_words_count(user_id)
        conn.commit()
        await state.clear()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()
