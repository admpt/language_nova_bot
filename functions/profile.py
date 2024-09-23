import logging
import sqlite3

import aiosqlite
from aiogram import types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from main import dp, create_connection, DB_FILE


# Функция для получения данных пользователя
async def get_user_data(user_id: int):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT full_name, elite_status, learned_words_count, topics_count FROM users WHERE user_id = ?",
            (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0], row[1], row[2], row[3]
            else:
                return None, None, 0, 0 # Вернём 0 для изученных слов, если пользователь не найден

@dp.message(F.text == "Профиль")
async def check_profile(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    full_name, elite_status, learned_words_count, topics_count = await get_user_data(user_id)

    full_name = f"{first_name} {last_name}" if first_name and last_name else first_name or last_name or "Пользователь"
    elite_status_text = "Элитный" if elite_status == "Yes" else "Free"
    if elite_status_text == "Элитный":
        elite_or_free_emoji = "💎"
    else:
        elite_or_free_emoji = "🆓"
    button = InlineKeyboardButton(text="🏆Leaders Page", callback_data="top_leaders")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await message.answer(
        f"*Имя: [{full_name}](tg://user?id={user_id})*\n\nИзученные слова: {learned_words_count}\nКоличество созданных тем: {topics_count}\n{elite_or_free_emoji}Статус: {elite_status_text}",
        parse_mode='MarkdownV2', reply_markup=keyboard
    )

async def get_top_users() -> list:
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
                "SELECT user_id, full_name, learned_words_count FROM users ORDER BY learned_words_count DESC LIMIT 15"
        ) as cursor:
            rows = await cursor.fetchall()
            return rows

@dp.callback_query(F.data == "top_leaders")
async def top_users(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    rows = await get_top_users()

    if not rows:
        await callback_query.answer("Топ-15 пользователей отсутствует.")
        return

    response = "*🔝Top-15 пользователей по изученным словам:*\n\n"
    for idx, (user_id, full_name, learned_words_count) in enumerate(rows, start=1):
        user_link = f"[{full_name}](tg://user?id={user_id})"  # Форматируем ссылку
        response += f"{idx}. {user_link} - {learned_words_count} слов\n"

    response = response.replace(".", "\\.").replace("-", "\\-")

    await callback_query.message.answer(response, parse_mode='MarkdownV2')

# Функция для обновления количества изученных слов
async def update_learned_words_count(user_id: int) -> int:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_dictionary WHERE user_id = ?", (user_id,))
        learned_words_count = cursor.fetchone()[0]
        cursor.execute("UPDATE users SET learned_words_count = ? WHERE user_id = ?", (learned_words_count, user_id))
        conn.commit()
        logging.info(f"Updated learned_words_count for user {user_id}: {learned_words_count}")
        return learned_words_count
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return 0
    finally:
        conn.close()

# Функция для обновления количества тем
async def update_learned_topics_count(user_id: int) -> None:
    logging.info(f"id {user_id}")
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT COUNT(*) FROM topics WHERE author_id = ?""", (user_id,))
        topics_count = cursor.fetchone()[0]
        cursor.execute("""UPDATE users SET topics_count = ? WHERE user_id = ?""", (topics_count, user_id))
        conn.commit()
        return topics_count
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return 0
    finally:
        conn.close()