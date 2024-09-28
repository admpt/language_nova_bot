import logging
import sqlite3

from aiogram import F, types, Bot, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, \
    InlineQueryResultArticle, InputTextMessageContent
import random

from shared import TOKEN, dp, DB_FILE, TranslationStates

bot = Bot(token=TOKEN)
repeat_words_router = Router()

@repeat_words_router.message(F.text == "Повторение слов", StateFilter(None))
async def repeat_words(message: types.Message, state: FSMContext) -> None:
    logging.info(f"repeat_words {message.from_user.id}")
    await state.clear()  # Сбрасываем состояние
    command = "поиск тем для повторения: "  # Определяем команду
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать тему", switch_inline_query_current_chat=command)]
    ])
    await message.answer("Выберите тему для повторения слов в ней:", reply_markup=kb)


@repeat_words_router.inline_query(F.query.startswith("поиск тем для повторения: "))
async def inline_query_handler_repeat(inline_query: types.InlineQuery) -> None:
    logging.info(f"inline_query_handler_repeat {inline_query.from_user.id}")
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
@repeat_words_router.message(lambda message: message.text.startswith("Для повторения была выбрана тема:"))
async def process_topic_selection_repeat(message: types.Message, state: FSMContext) -> None:
    logging.info(f"process_topic_selection_repeat {message.from_user.id}")
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
                 InlineKeyboardButton(text="ENG-RU", callback_data=f"eng_ru:{topic_id}")],
                [InlineKeyboardButton(text="Найти слово", callback_data=f"find_word_in_topic:{topic_id}")]
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


@repeat_words_router.message(F.text == "Прекратить повтор")
async def stop_translation(message: types.Message, state: FSMContext):
    logging.info(f"stop_translation {message.from_user.id}")
    await state.clear()  # Сбрасываем состояние
    kb = [
        [KeyboardButton(text="Словарь"), KeyboardButton(text="Профиль")],
        [KeyboardButton(text="Повторение слов")],
        [KeyboardButton(text="Грамматика")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Повторение прекращено.", reply_markup=keyboard)


# Состояние для хранения текущего слова
@repeat_words_router.callback_query(lambda c: c.data.startswith("eng_ru:"))
async def start_eng_ru_translation(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"start_eng_ru_translation {callback_query.from_user.id}")
    topic_id = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id

    await state.update_data(topic_id=topic_id)
    await state.set_state(TranslationStates.ENG_RU)
    await ask_for_ru_translation(callback_query.message, user_id, topic_id, state)

@repeat_words_router.message(F.text=='ask_for_ru_translation')
async def ask_for_ru_translation(message: types.Message, user_id: int, topic_id: int, state: FSMContext):
    logging.info(f"ask_for_ru_translation {message.from_user.id}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT word, translation FROM user_dictionary WHERE topic_id = ? AND user_id = ?",
                       (topic_id, user_id))
        words = cursor.fetchall()
        if words:
            word, translation = random.choice(words)
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

@repeat_words_router.message(lambda message: message.text.strip() != "Прекратить повтор", TranslationStates.ENG_RU)
async def check_eng_ru_translation(message: types.Message, state: FSMContext):
    logging.info(f"check_eng_ru_translation {message.from_user.id}")
    data = await state.get_data()
    current_translation = data.get('current_translation')

    if current_translation is None:
        await message.answer("Ошибка: текущее значение перевода не найдено.")
        return

    logging.info(f"User input: '{message.text.strip().lower()}', Expected: '{current_translation.lower()}'")

    if message.text.strip().lower() == current_translation.strip().lower():
        await message.answer("Правильно!")
        await ask_for_ru_translation(message, message.from_user.id, data.get('topic_id'), state)
    else:
        stop_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Прекратить повтор")]]
        )
        await message.answer("Неправильно. Попробуйте еще раз.", reply_markup=stop_kb, resize_keyboard=True)




@repeat_words_router.callback_query(lambda c: c.data.startswith("ru_eng:"))
async def start_ru_eng_translation(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"start_ru_eng_translation {callback_query.from_user.id}")
    await state.clear()
    topic_id = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    await state.update_data(topic_id=topic_id)
    await state.set_state(TranslationStates.RU_ENG)
    await ask_for_eng_translation(callback_query.message, user_id, topic_id, state)

@repeat_words_router.message(F.text=='ask_for_eng_translation')
async def ask_for_eng_translation(message: types.Message, user_id: int, topic_id: int, state: FSMContext):
    logging.info(f"ask_for_eng_translation {message.from_user.id}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT translation, word FROM user_dictionary WHERE topic_id = ? AND user_id = ?",
                       (topic_id, user_id))
        words = cursor.fetchall()

        if words:
            translation, word = random.choice(words)  # translation - русское, word - английское

            stop_kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Прекратить повтор")]]
            )

            await message.answer(f"Слово: *{translation}*\nНапишите перевод на английском:", reply_markup=stop_kb, resize_keyboard=True)
            await state.update_data(current_word=word, current_translation=translation)
        else:
            await message.answer("В этой теме нет слов.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Произошла ошибка при получении слов.")
    finally:
        conn.close()

@repeat_words_router.message(lambda message: message.text.strip() != "Прекратить повтор", TranslationStates.RU_ENG)
async def check_ru_eng_translation(message: types.Message, state: FSMContext):
    logging.info(f"check_ru_eng_translation {message.from_user.id}")
    data = await state.get_data()
    current_word = data.get('current_word')  # Это английское слово

    if current_word and message.text.strip().lower() == current_word.lower():
        await message.answer("Правильно!")
        await ask_for_eng_translation(message, message.from_user.id, data.get('topic_id'), state)
    else:
        stop_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Прекратить повтор")]]
        )
        await message.answer("Неправильно. Попробуйте еще раз.", reply_markup=stop_kb, resize_keyboard=True)


# @repeat_words_router.callback_query(lambda c: c.data.startswith("find_word_in_topic:"))
