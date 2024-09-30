import datetime
import sqlite3
import logging
from aiogram import types, Bot, Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from shared import dp, DB_FILE, create_connection, TranslationStates
from token_of_bot import API_TOKEN

TOKEN = API_TOKEN
bot = Bot(token=TOKEN)
start_router = Router()

@start_router.message(F.text.startswith("/start"))
async def start_command_handler(message: types.Message, state: FSMContext):
    command = message.text.split(maxsplit=1)
    referral_code = command[1] if len(command) > 1 else None
    if referral_code and referral_code.startswith('='):
        referral_code = referral_code[1:]  # Удаляем '=' если есть
    await process_start_command(message, referral_code, state, upsert_user)

async def process_start_command(message: types.Message, referral_code: str, state: FSMContext, upsert_user_func) -> None:
    await state.clear()  # Сбрасываем состояние
    logging.info(f"process_start_command {message.from_user.id}")

    logging.info(f"Referral code: {referral_code}")

    button = InlineKeyboardButton(text="Начать обучение!", callback_data="start_learning")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    await message.answer("Добро пожаловать! Нажмите кнопку ниже, чтобы начать изучение:", reply_markup=keyboard)

    try:
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        full_name = f"{first_name} {last_name}" if first_name and last_name else first_name or last_name or ""

        current_time = datetime.datetime.now()

        referrer_id = await get_user_id_by_referral_code(referral_code) if referral_code else None

        await upsert_user_func(message.from_user.id, message.from_user.username or '', full_name, referral_code, referrer_id)

        logging.info(f"User data updated for {message.from_user.id}")

    except Exception as e:
        logging.error(f"Error while updating user data: {e}")

async def get_user_id_by_referral_code(referral_code: str) -> int:
    """Получаем user_id по реферальному коду"""
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (referral_code,))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return None
    finally:
        conn.close()

@start_router.callback_query(lambda c: c.data == 'start_learning')
async def process_start_learning(callback_query: types.CallbackQuery) -> None:
    logging.info(f"process_start_learning {callback_query.from_user.id}")
    user_id = callback_query.from_user.id
    await bot.answer_callback_query(callback_query.id)

    kb = [
        [KeyboardButton(text="Словарь"), KeyboardButton(text="Профиль")],
        [KeyboardButton(text="Повторение слов")],
        [KeyboardButton(text="Грамматика")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await bot.send_message(user_id, "Вы начали изучение! Что вы хотите сделать?", reply_markup=keyboard)

async def upsert_user(user_id: int, username_tg: str, full_name: str, referral_code: str = None,
                      referrer_id: int = None, balance: int = 0, elite_status: str = 'No',
                      learned_words_count: int = 0, elite_start_date: str = None) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        unique_referral_code = str(user_id)

        cursor.execute("""INSERT INTO users (user_id, username_tg, full_name, balance, elite_status, learned_words_count, referral_code, referred_by, elite_start_date)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                          ON CONFLICT(user_id) DO UPDATE SET
                              username_tg = excluded.username_tg,
                              full_name = excluded.full_name,
                              balance = excluded.balance,
                              elite_status = excluded.elite_status,
                              learned_words_count = excluded.learned_words_count,
                              referral_code = excluded.referral_code,
                              referred_by = excluded.referred_by,
                              elite_start_date = excluded.elite_start_date
                       """, (
            user_id, username_tg, full_name, balance, elite_status, learned_words_count, unique_referral_code,
            referrer_id, elite_start_date))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()

async def check_elite_status(user_id: int) -> str:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT elite_status, elite_start_date FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            elite_status, elite_start_date = result
            if elite_status == 'Yes':
                start_date = datetime.datetime.strptime(elite_start_date, '%Y-%m-%d %H:%M:%S')
                if (datetime.datetime.now() - start_date).days >= 3:
                    cursor.execute("UPDATE users SET elite_status = 'No', elite_start_date = NULL WHERE user_id = ?", (user_id,))
                    conn.commit()
                    return 'No'
            return elite_status
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return 'No'
    finally:
        conn.close()

@start_router.message(F.text)
async def handle_any_text(message: types.Message, state: FSMContext) -> None:
    logging.info(f"handle_any_text {message.from_user.id}")
    current_state = await state.get_state()
    logging.info(current_state)
    if current_state is not None and current_state not in {TranslationStates.ENG_RU.state, TranslationStates.RU_ENG.state, TranslationStates.repeat_irregular_verbs.state}:
        await state.clear()
        await message.answer("Текущее действие отменено. Выберите новое действие.")
