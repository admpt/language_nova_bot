import aiosqlite
import logging
from aiogram import types, F
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from main import dp


@dp.message(F.text == "Словарь")
async def learning(message: types.Message) -> None:
    user_id = message.from_user.id

    kb = [
        [KeyboardButton(text="Добавить тему"), KeyboardButton(text="Добавить слова")],
        [KeyboardButton(text="Повторение слов")],
        [KeyboardButton(text="🔙Назад")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer("Что вы хотите сделать дальше?\nДоделать описание", reply_markup=keyboard)