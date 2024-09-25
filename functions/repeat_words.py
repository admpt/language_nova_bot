import logging
import sqlite3

from aiogram import F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, \
    InlineQueryResultArticle, InputTextMessageContent
from main import dp, Form, DB_FILE, TOKEN
import random


bot = Bot(token=TOKEN)

@dp.message(F.text == "Повторение слов")
async def repeat_words(message: types.Message, state: FSMContext) -> None:
    await state.clear()  # Сбрасываем состояние
    command = "поиск тем для повторения: "  # Определяем команду
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать тему", switch_inline_query_current_chat=command)]
    ])
    await message.answer("Выберите тему для повторения слов в ней:", reply_markup=kb)


@dp.inline_query(F.query.startswith("поиск тем для повторения: "))
async def inline_query_handler_repeat(inline_query: types.InlineQuery) -> None:
    query = inline_query.query[len("поиск тем для повторения: "):].strip()  # Убираем команду
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
                    message_text=f"Для повторения была выбрана тема: {item[1]}"
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
@dp.message(lambda message: message.text.startswith("Для повторения была выбрана тема:"))
async def process_topic_selection_repeat(message: types.Message, state: FSMContext) -> None:
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

            message_text = f"Название темы: *{topic_name}*\nКоличество слов: {word_count}" if word_count > 0 else f"*{topic_name}*\nКоличество слов: 0"

            # Дальнейшие действия
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="RU-ENG", callback_data=f"ru_eng:{topic_id}"),
                 InlineKeyboardButton(text="ENG-RU", callback_data=f"eng_ru:{topic_id}")]
            ])
            await message.answer(message_text, parse_mode='Markdown', reply_markup=kb)
            await state.clear()  # Очищаем состояние после выбора темы
        else:
            await message.answer("Тема не найдена.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Произошла ошибка при получении данных.")
    finally:
        conn.close()



# Состояние для хранения текущего слова
@dp.callback_query(lambda c: c.data.startswith("eng_ru:"))
async def start_eng_ru_translation(callback_query: types.CallbackQuery, state: FSMContext):
    topic_id = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id

    # Сохраняем тему в состоянии
    await state.update_data(topic_id=topic_id)
    await ask_for_translation(callback_query.message, user_id, topic_id, state)

@dp.message(F.text == "Прекратить повтор")
async def stop_translation(message: types.Message, state: FSMContext):
    await state.clear()
    kb = [
        [KeyboardButton(text="Словарь"), KeyboardButton(text="Профиль")],
        [KeyboardButton(text="Повторение слов")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Повторение прекращено.", reply_markup=keyboard)


async def ask_for_translation(message: types.Message, user_id: int, topic_id: int, state: FSMContext):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT word, translation FROM user_dictionary WHERE topic_id = ? AND user_id = ?",
                       (topic_id, user_id))
        words = cursor.fetchall()

        if words:
            word, translation = random.choice(words)  # Случайное слово

            # Создаем клавиатуру для прекращения повторений
            stop_kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Прекратить повтор")]]
            )

            await message.answer(f"Слово: *{word}*\nНапишите перевод на русском:", reply_markup=stop_kb, resize_keyboard=True)
            await state.update_data(current_word=word, current_translation=translation)
        else:
            await message.answer("В этой теме нет слов.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Произошла ошибка при получении слов.")
    finally:
        conn.close()


@dp.message(lambda message: message.text.strip() != "Прекратить повтор")
async def check_translation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_translation = data.get('current_translation')

    if current_translation and message.text.strip().lower() == current_translation.lower():
        await message.answer("Правильно!")
        await ask_for_translation(message, message.from_user.id, data.get('topic_id'), state)
    else:
        # Создаем клавиатуру для прекращения повторений
        stop_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Прекратить повтор")]]
        )
        await message.answer("Неправильно. Попробуйте еще раз.", reply_markup=stop_kb, resize_keyboard=True)

