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
        cursor.execute("""
        INSERT INTO users (user_id, username_tg, full_name, balance, elite_status, learned_words_count)
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


@dp.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    logging.info(f"Received /start command from {message.from_user.id}")

    # Создание инлайн-кнопки
    button = InlineKeyboardButton(text="Начать изучать!", callback_data="start_learning")
    # Создание клавиатуры с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    # Отправка сообщения с инлайн-кнопкой
    await message.answer("Добро пожаловать! Нажмите кнопку ниже, чтобы начать изучение:", reply_markup=keyboard)

    # Обновление или добавление пользователя в базу данных
    try:
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name

        # Формируем `full_name` в зависимости от наличия имени и фамилии
        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
        elif first_name:
            full_name = first_name
        elif last_name:
            full_name = last_name
        else:
            full_name = ""

        # Обновляем или добавляем пользователя в базу данных
        upsert_user(message.from_user.id, message.from_user.username or '', full_name)
        logging.info(f"User data updated for {message.from_user.id}")
    except Exception as e:
        logging.error(f"Error while updating user data: {e}")


@dp.callback_query(lambda c: c.data == 'start_learning')
async def process_start_learning(callback_query: types.CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    await bot.answer_callback_query(callback_query.id)

    # Отправка сообщения с кнопками "Словарь" и "Настройки"
    kb = [
        [types.KeyboardButton(text="Словарь")],
        [types.KeyboardButton(text="Настройки")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await bot.send_message(user_id, "Вы начали изучение! В чем могу помочь?", reply_markup=keyboard)


@dp.message(F.text == "Словарь")
async def show_dictionary(message: types.Message) -> None:
    user_id = message.from_user.id
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT word, translation FROM user_dictionary WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()

        if rows:
            dictionary_entries = "\n".join([f"{word}: {translation}" for word, translation in rows])
            await message.answer(f"Ваш словарь:\n{dictionary_entries}")
        else:
            await message.answer("Ваш словарь пуст.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Ошибка при получении данных словаря.")
    finally:
        conn.close()


@dp.message(F.text == "Добавить слово")
async def add_word(message: types.Message) -> None:
    user_id = message.from_user.id
    # Попросим пользователя предоставить слово и перевод
    await message.answer("Введите слово на английском языке и перевод через пробел. Например: 'apple яблоко'")


@dp.message(lambda m: len(m.text.split()) == 2)
async def process_add_word(message: types.Message) -> None:
    user_id = message.from_user.id
    word, translation = message.text.split()
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_dictionary (user_id, word, translation)
            VALUES (?, ?, ?)
        """, (user_id, word, translation))

        # Обновляем количество изученных слов
        update_learned_words_count(user_id)

        conn.commit()
        await message.answer(f"Слово '{word}' добавлено в ваш словарь!")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Ошибка при добавлении слова.")
    finally:
        conn.close()


def update_learned_words_count(user_id: int) -> None:
    """Обновление количества изученных слов для пользователя"""
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()

        # Подсчитываем количество слов в словаре пользователя
        cursor.execute("""
            SELECT COUNT(*) FROM user_dictionary WHERE user_id = ?
        """, (user_id,))
        learned_words_count = cursor.fetchone()[0]

        # Обновляем количество изученных слов в таблице `users`
        cursor.execute("""
            UPDATE users SET learned_words_count = ? WHERE user_id = ?
        """, (learned_words_count, user_id))

        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Error while polling: {e}")


if __name__ == "__main__":
    asyncio.run(main())