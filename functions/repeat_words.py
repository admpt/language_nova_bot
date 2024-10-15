import logging
import sqlite3
from gc import callbacks
from uuid import uuid4

from aiogram import F, types, Bot, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, \
    InlineQueryResultArticle, InputTextMessageContent
import random

from shared import TOKEN, dp, DB_FILE, TranslationStates, DeleteStates

bot = Bot(token=TOKEN)
repeat_words_router = Router()
global current_topic_id


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
    global current_topic_id
    logging.info(f"process_topic_selection_repeat {message.from_user.id}")
    topic_name = message.text.split(": ", 1)[-1]

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, visible FROM topics WHERE content = ?", (topic_name,))
        topic = cursor.fetchone()

        if topic:
            current_topic_id, is_visible = topic  # Устанавливаем глобальную переменную и статус видимости

            cursor.execute("SELECT COUNT(*) FROM user_dictionary WHERE topic_id = ?", (current_topic_id,))
            word_count = cursor.fetchone()[0]

            message_text = f"Название темы: *{topic_name}*\nКоличество слов: {word_count}\nСтатус: {'Публичная' if is_visible else 'Приватная'}"
            command = f"поиск слова в теме {topic_name}: "

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="RU-ENG", callback_data=f"ru_eng:{current_topic_id}"),
                 InlineKeyboardButton(text="ENG-RU", callback_data=f"eng_ru:{current_topic_id}")],
                [InlineKeyboardButton(text="Слова в теме", callback_data=f"show_words:{current_topic_id}")],
                # [InlineKeyboardButton(text="Найти слово", switch_inline_query_current_chat=command)],
                [InlineKeyboardButton(text="Сделать приватной" if is_visible else "Сделать публичной",
                                     callback_data=f"toggle_visibility:{current_topic_id}")]
            ])
            await message.answer(message_text, parse_mode='Markdown', reply_markup=kb)
            await state.clear()
        else:
            await message.answer("Тема не найдена.")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Произошла ошибка при получении данных.")
    finally:
        conn.close()

@repeat_words_router.callback_query(F.data.startswith("toggle_visibility:"))
async def toggle_visibility(callback_query: types.CallbackQuery) -> None:
    global current_topic_id
    topic_id = int(callback_query.data.split(":")[1])

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT visible FROM topics WHERE id = ?", (topic_id,))
        result = cursor.fetchone()

        if result:
            current_visibility = result[0]
            new_visibility = 1 - current_visibility  # Меняем статус

            # Обновляем статус в базе данных
            cursor.execute("UPDATE topics SET visible = ? WHERE id = ?", (new_visibility, topic_id))
            conn.commit()

            # Получаем новое название темы и количество слов
            cursor.execute("SELECT content FROM topics WHERE id = ?", (topic_id,))
            topic_name = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM user_dictionary WHERE topic_id = ?", (topic_id,))
            word_count = cursor.fetchone()[0]

            status_text = "Публичный" if new_visibility else "Приватный"
            message_text = f"Название темы: *{topic_name}*\nКоличество слов: {word_count}\nСтатус: {status_text}"

            await callback_query.answer(f"Статус темы изменен на {status_text}.", show_alert=True)

            # Создаём новую клавиатуру с обновлённой кнопкой
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="RU-ENG", callback_data=f"ru_eng:{topic_id}"),
                 InlineKeyboardButton(text="ENG-RU", callback_data=f"eng_ru:{topic_id}")],
                [InlineKeyboardButton(text="Слова в теме", callback_data=f"show_words:{topic_id}")],
                [InlineKeyboardButton(text="Сделать приватной" if new_visibility else "Сделать публичной",
                                     callback_data=f"toggle_visibility:{topic_id}")]
            ])

            # Обновляем сообщение с новой информацией и клавиатурой
            await callback_query.message.edit_text(message_text, parse_mode='Markdown', reply_markup=kb)
        else:
            await callback_query.answer("Тема не найдена.", show_alert=True)
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await callback_query.answer("Произошла ошибка при изменении видимости темы.", show_alert=True)
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


@repeat_words_router.callback_query(F.data.startswith("show_words:"))
async def show_words(callback_query: types.CallbackQuery) -> None:
    topic_id = int(callback_query.data.split(":")[1])

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT word, translation FROM user_dictionary WHERE topic_id = ?", (topic_id,))
        words = cursor.fetchall()

        words = [(word[0], word[1]) for word in words]

        if not words:
            await callback_query.answer("В этой теме нет слов.", show_alert=True)
            return

        current_page = 0
        await send_word_page(callback_query.message, words, current_page, topic_id)

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await callback_query.answer("Произошла ошибка при получении слов.", show_alert=True)
    finally:
        conn.close()


async def send_word_page(message: types.Message, words: list, page: int, topic_id: int) -> None:
    words_per_page = 15
    start_index = page * words_per_page
    end_index = start_index + words_per_page

    words_to_display = words[start_index:end_index]
    words_text = "\n".join(
        f"{i + 1 + start_index}. {word} - {translation}" for i, (word, translation) in enumerate(words_to_display))

    # Создаем клавиатуру для навигации
    nav_kb = []
    if page > 0:
        nav_kb.append(InlineKeyboardButton(text="Назад", callback_data=f"word_page:{page - 1}:{topic_id}"))
    if end_index < len(words):
        nav_kb.append(InlineKeyboardButton(text="Вперёд", callback_data=f"word_page:{page + 1}:{topic_id}"))

    # Создаем клавиатуру для удаления слова
    delete_kb = [[InlineKeyboardButton(text="Удалить слово", callback_data=f"delete_word:{topic_id}")]]

    # Объединяем навигационную клавиатуру с клавиатурой для удаления
    full_kb = InlineKeyboardMarkup(inline_keyboard=[nav_kb, *delete_kb])

    await message.edit_text(f"Слова:\n{words_text}", reply_markup=full_kb)


@repeat_words_router.callback_query(F.data.startswith("delete_word:"))
async def delete_word(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    topic_id = int(callback_query.data.split(":")[1])

    kb = [
        [KeyboardButton(text="Отменить действие")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await callback_query.message.answer("Введите номер слова или слово на английском для удаления.", reply_markup=keyboard)

    # Установите состояние
    await state.set_state(DeleteStates.waiting_for_deletion.state)
    # Сохраняем topic_id в состоянии
    await state.update_data(topic_id=topic_id)


@repeat_words_router.message(StateFilter(DeleteStates.waiting_for_deletion))
async def process_delete_word(message: types.Message, state: FSMContext) -> None:
    input_text = message.text
    data = await state.get_data()
    topic_id = data.get('topic_id')
    user_id = message.from_user.id  # Получаем user_id

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Проверяем наличие слова в базе данных
        cursor.execute("DELETE FROM user_dictionary WHERE user_id = ? AND topic_id = ? AND word = ?",
                       (user_id, topic_id, input_text))
        if cursor.rowcount > 0:
            conn.commit()
            kb = [
                [KeyboardButton(text="Словарь"), KeyboardButton(text="Профиль")],
                [KeyboardButton(text="Повторение слов")],
                [KeyboardButton(text="Грамматика")],
            ]
            keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
            await message.answer(f'Слово "{input_text}" успешно удалено.', reply_markup=keyboard)


        else:
            kb = [
                [KeyboardButton(text="Словарь"), KeyboardButton(text="Профиль")],
                [KeyboardButton(text="Повторение слов")],
                [KeyboardButton(text="Грамматика")],
            ]
            keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
            await message.answer(f'Слово "{input_text}" не найдено.', reply_markup=keyboard)

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Произошла ошибка при удалении слова.")
    finally:
        conn.close()
        await state.clear()  # Завершение состояния



@repeat_words_router.callback_query(F.data.startswith("word_page:"))
async def navigate_words(callback_query: types.CallbackQuery) -> None:
    _, page_str, topic_id_str = callback_query.data.split(":")
    page = int(page_str)
    topic_id = int(topic_id_str)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT word, translation FROM user_dictionary WHERE topic_id = ?", (topic_id,))
        words = cursor.fetchall()

        words = [(word[0], word[1]) for word in words]

        if not words:
            await callback_query.answer("В этой теме нет слов.", show_alert=True)
            return

        await send_word_page(callback_query.message, words, page, topic_id)

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await callback_query.answer("Произошла ошибка при получении слов.", show_alert=True)
    finally:
        conn.close()
