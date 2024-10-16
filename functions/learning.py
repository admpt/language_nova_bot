import aiosqlite
import logging
from aiogram import types, F, Router
from aiogram.filters import StateFilter
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from shared import dp

learning_router = Router()

@learning_router.message(F.text == "Словарь", StateFilter(None))
async def learning(message: types.Message) -> None:
    logging.info(f"learning {message.from_user.id}")
    user_id = message.from_user.id

    kb = [
        [KeyboardButton(text="Добавить тему"), KeyboardButton(text="Добавить слова")],
        [KeyboardButton(text="Повторение слов")],
        [KeyboardButton(text="🔙Назад")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer("Вы открываете словарь. Что вы хотите сделать дальше?", reply_markup=keyboard)