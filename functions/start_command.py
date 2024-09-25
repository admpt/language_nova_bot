import sqlite3

from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
import logging
from token_of_bot import API_TOKEN

TOKEN = API_TOKEN
from main import dp, create_connection, DB_FILE

bot = Bot(token=TOKEN)

async def process_start_command(message: types.Message, state: FSMContext, upsert_user) -> None:
    await state.clear()  # Сбрасываем состояние
    logging.info(f"Received /start command from {message.from_user.id}")

    button = InlineKeyboardButton(text="Начать обучение!", callback_data="start_learning")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await message.answer("Добро пожаловать! Нажмите кнопку ниже, чтобы начать изучение:", reply_markup=keyboard)

    # Обновляем данные пользователя
    try:
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        full_name = f"{first_name} {last_name}" if first_name and last_name else first_name or last_name or ""

        await upsert_user(message.from_user.id, message.from_user.username or '', full_name)
        logging.info(f"User data updated for {message.from_user.id}")
    except Exception as e:
        logging.error(f"Error while updating user data: {e}")

# Обработка нажатия на кнопку "Начать обучение!"
@dp.callback_query(lambda c: c.data == 'start_learning')
async def process_start_learning(callback_query: types.CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    await bot.answer_callback_query(callback_query.id)

    kb = [
        [KeyboardButton(text="Словарь"), KeyboardButton(text="Профиль")],
        [KeyboardButton(text="Повторение слов")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await bot.send_message(user_id, "Вы начали изучение! Что вы хотите сделать?", reply_markup=keyboard)

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
