import logging
import sqlite3
from uuid import uuid4
import random

from aiogram import types, F, Bot, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent, \
    ReplyKeyboardMarkup, KeyboardButton
from shared import DB_FILE, TOKEN, TranslationStates

bot = Bot(token=TOKEN)

logging.basicConfig(level=logging.INFO)
grammar_router = Router()

# Обработчик сообщения "Грамматика"
@grammar_router.message(F.text=="Грамматика", StateFilter(None))
async def grammar(message: types.Message, state: FSMContext) -> None:
    logging.info(f"grammar {message.from_user.id}")
    await state.clear()  # Сбрасываем состояние
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Irregular Verbs", callback_data="irregular_verbs"),
         InlineKeyboardButton(text="Таблица Времен", callback_data="time_select")]
    ])
    await message.answer("Выберите тему по грамматике:", reply_markup=kb)


# Обработчик callback запроса для "Irregular Verbs"
@grammar_router.callback_query(F.data == "irregular_verbs")
async def handle_irregular_verbs(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"handle_irregular_verbs {callback_query.from_user.id}")
    command = "введите глагол в форме Infinitive: "  # Определяем команду
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Неправильные глаголы", switch_inline_query_current_chat=command)],
        [InlineKeyboardButton(text="Продолжи ряд", callback_data="continue_series")],
    ])
    await callback_query.message.answer(
        "Вы выбрали тему: Неправильные глаголы.\nПожалуйста, введите глагол в форме инфинитива:",
        reply_markup=kb
    )
    await callback_query.answer()  # Подтверждаем callback


# Обработчик инлайн-запроса
@grammar_router.inline_query(lambda query: query.query.startswith("введите глагол в форме Infinitive: "))
async def inline_query_handler_irregular(inline_query: types.InlineQuery) -> None:
    logging.info(f"inline_query_handler_irregular {inline_query.from_user.id}")
    command_prefix = "введите глагол в форме Infinitive: "
    query_text = inline_query.query[len(command_prefix):].strip()

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Поиск по инфинитиву или второму инфинитиву
            cursor.execute("""
                SELECT v1, v1_second, v2_first, v2_second, v3_first, v3_second, 
                       first_translation, second_translation, third_translation
                FROM irregular_verbs
                WHERE v1 LIKE ? OR v1_second LIKE ?
                LIMIT 50
                """, (f'%{query_text}%', f'%{query_text}%'))
            results = cursor.fetchall()

        items = []
        items = items[:50]
        for item in results:
            # Генерация уникального ID для каждого результата
            result_id = str(uuid4())
            title = item[0] if item[0] else 'Unknown Verb'  # Используем v1 как заголовок
            items.append(
                InlineQueryResultArticle(
                    id=result_id,
                    title=title,
                    input_message_content=InputTextMessageContent(
                        message_text=f"Глагол: {item[0]}"
                    )
                )
            )

        if not items:
            items = [
                InlineQueryResultArticle(
                    id="no_results",
                    title="Нет доступных глаголов",
                    input_message_content=InputTextMessageContent(message_text="Не найдено.")
                )
            ]

        # Отправка результатов инлайн-запроса
        await inline_query.answer(results=items, cache_time=1)

    except sqlite3.OperationalError as e:
        logging.error(f"Database error: {e}")
        await inline_query.answer(results=[])


# Обработчик сообщения после выбора глагола
@grammar_router.message(lambda message: message.text.startswith("Глагол: "))
async def process_topic_selection_repeat(message: types.Message, state: FSMContext) -> None:
    logging.info(f"process_topic_selection_repeat {message.from_user.id}")
    await state.clear()
    verb_name = message.text.split(": ", 1)[-1].strip()

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Поиск глагола по v1 или v1_second
            cursor.execute("""
                SELECT v1, v1_second, v2_first, v2_second, v3_first, v3_second, 
                       first_translation, second_translation, third_translation
                FROM irregular_verbs
                WHERE v1 = ? OR v1_second = ?
            """, (verb_name, verb_name))
            verb = cursor.fetchone()

        if verb:
            # Разделяем полученные данные
            v1, v1_second, v2_first, v2_second, v3_first, v3_second, first_translation, second_translation, third_translation = verb

            parts = []

            # Инфинитив
            if v1 and v1_second:
                infinitive = f"{v1} / {v1_second}"
            elif v1:
                infinitive = v1
            else:
                infinitive = "Неизвестно"
            parts.append(f"*Infinitive:* {infinitive}")

            # Past Simple
            if v2_first and v2_second:
                past_simple = f"{v2_first} / {v2_second}"
            elif v2_first:
                past_simple = v2_first
            else:
                past_simple = "Неизвестно"
            parts.append(f"*Past Simple:* {past_simple}")

            # Past Participle
            if v3_first and v3_second:
                past_participle = f"{v3_first} / {v3_second}"
            elif v3_first:
                past_participle = v3_first
            else:
                past_participle = "Неизвестно"
            parts.append(f"*Past Participle:* {past_participle}")

            # Переводы
            translations = []
            if first_translation:
                translations.append(first_translation)
            if second_translation:
                translations.append(second_translation)
            if third_translation:
                translations.append(third_translation)
            if len(translations) > 1:
                translations_text = ", ".join(translations)
                parts.append(f"*Translations:* {translations_text}")
            if len(translations) == 1:
                translations_text = ", ".join(translations)
                parts.append(f"*Translation:* {translations_text}")
            # Объединяем все части в одно сообщение

            message_text = "\n".join(parts)

            # Отправляем сообщение пользователю
            await message.answer(message_text, parse_mode='Markdown')
        else:
            await message.answer("Глагол не найден.")

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Произошла ошибка при получении данных.")


# Функция для получения случайного глагола
async def get_random_verb():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT v1, v1_second, v2_first, v2_second, v3_first, v3_second, first_translation, second_translation, third_translation FROM irregular_verbs")
        verbs = cursor.fetchall()
        if verbs:
            return random.choice(verbs)
    return None


@grammar_router.callback_query(F.data == "continue_series")
async def continue_series(message_or_callback_query, state: FSMContext):
    logging.info(f"continue_series {message_or_callback_query.from_user.id}")
    verb_data = await get_random_verb()

    if not verb_data:
        await message_or_callback_query.answer("Нет доступных глаголов в базе данных.")
        return

    await state.update_data(verb_data=verb_data)
    v1, v1_second = verb_data[0], verb_data[1]
    infinitive = v1 or v1_second

    if isinstance(message_or_callback_query, types.CallbackQuery):
        await message_or_callback_query.message.answer(f"Введите Past Simple для глагола: {infinitive}")
    else:
        await message_or_callback_query.answer(f"Введите Past Simple для глагола: {infinitive}")

    await state.set_state(TranslationStates.ask_past_simple)


@grammar_router.message(TranslationStates.ask_past_simple)
async def ask_past_simple(message: types.Message, state: FSMContext):
    data = await state.get_data()
    verb_data = data.get('verb_data')

    if not verb_data:
        await message.answer("Нет данных о глаголе.")
        return

    v2_first, v2_second = verb_data[2], verb_data[3]
    user_input = message.text.strip()

    if user_input in [v2_first, v2_second]:
        await message.answer(f"Правильно! Теперь введите Past Participle для глагола: {verb_data[0] or verb_data[1]}.")
        await state.set_state(TranslationStates.ask_past_participle)
    else:
        correct_answer = ", ".join(filter(None, [v2_first, v2_second]))
        await message.answer(f"Неправильно! Правильный ответ: {correct_answer}.")
        await message.answer(f"Введите Past Participle для глагола: {verb_data[0] or verb_data[1]}")
        await state.set_state(TranslationStates.ask_past_participle)


@grammar_router.message(TranslationStates.ask_past_participle)
async def ask_past_participle(message: types.Message, state: FSMContext):
    data = await state.get_data()
    verb_data = data.get('verb_data')
    infinitive = verb_data[0] or verb_data[1]

    if not verb_data:
        await message.answer("Нет данных о глаголе.")
        return

    v3_first, v3_second = verb_data[4], verb_data[5]
    user_input = message.text.strip()

    if user_input in [v3_first, v3_second]:
        await message.answer("Совершенно верно! Теперь введите перевод слова.")
        await state.update_data(correct_translation=next((t for t in verb_data[6:] if t), "Неизвестно"))
        await message.answer(f"Переведите глагол {infinitive} на русский язык:")
        await state.set_state(TranslationStates.check_translation)
    else:
        correct_answer = ", ".join(filter(None, [v3_first, v3_second]))
        await message.answer(f"Неправильно. Правильный ответ: {correct_answer}.")
        await message.answer(f"Переведите глагол {infinitive} на русский язык:")
        await state.update_data(correct_translation=next((t for t in verb_data[6:] if t), "Неизвестно"))
        await state.set_state(TranslationStates.check_translation)


@grammar_router.message(TranslationStates.check_translation)
async def check_translation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    correct_translation = data.get('correct_translation')
    verb_data = data.get('verb_data')
    user_input = message.text.strip()

    # Составляем список правильных переводов
    correct_translations = [correct_translation] + [t for t in verb_data[6:] if t]

    # Если перевод правильный
    if user_input in correct_translations:
        infinitive = verb_data[0] or verb_data[1]
        v2_first = verb_data[2]
        v2_second = verb_data[3]
        v3_first = verb_data[4]
        v3_second = verb_data[5]
        translations = verb_data[6:]

        past_simple_forms = [form for form in [v2_first, v2_second] if form]
        past_participle_forms = [form for form in [v3_first, v3_second] if form]
        translations = [t for t in translations if t]

        response_parts = [f"Глагол: {infinitive}"]
        if past_simple_forms:
            response_parts.append(f"Past Simple: {' / '.join(past_simple_forms)}")
        if past_participle_forms:
            response_parts.append(f"Past Participle: {' / '.join(past_participle_forms)}")
        if translations:
            response_parts.append(f"Переводы: {' / '.join(translations)}")

        await message.answer("Совершенно верно!\n" + '\n'.join(response_parts))

    # Если перевод неправильный
    else:
        infinitive = verb_data[0] or verb_data[1]
        v2_first = verb_data[2]
        v2_second = verb_data[3]
        v3_first = verb_data[4]
        v3_second = verb_data[5]
        translations = verb_data[6:]

        past_simple_forms = [form for form in [v2_first, v2_second] if form]
        past_participle_forms = [form for form in [v3_first, v3_second] if form]
        translations = [t for t in translations if t]

        response_parts = [f"Глагол: {infinitive}"]
        if past_simple_forms:
            response_parts.append(f"Past Simple: {' / '.join(past_simple_forms)}")
        if past_participle_forms:
            response_parts.append(f"Past Participle: {' / '.join(past_participle_forms)}")
        if translations:
            response_parts.append(f"Переводы: {' / '.join(translations)}")

        await message.answer(
            f"Неправильно! Правильный перевод: {correct_translation}.\n\nЗапомните!\n" + '\n'.join(response_parts))

    # Переходим к следующему слову
    await continue_series(message, state)


@grammar_router.callback_query(F.data == "time_select")
async def handle_type_time_select(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"handle_type_time_select {callback_query.from_user.id}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Active Voice", callback_data="select_active_voice"),
         InlineKeyboardButton(text="Passive Voice", callback_data="select_passive_voice")
        ]
    ])
    await callback_query.message.answer("Выберите время:", reply_markup=kb)


@grammar_router.callback_query(F.data == "select_active_voice")
async def handle_active_voice(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"handle_active_voice {callback_query.from_user.id}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Present Simple", callback_data="active_present_simple"),
         InlineKeyboardButton(text="Present Continuous", callback_data="active_present_continuous"),
         InlineKeyboardButton(text="Present Perfect", callback_data="active_present_perfect"),
         InlineKeyboardButton(text="Present Perfect Continuous", callback_data="active_present_perfect_continuous"),
         ],
        [InlineKeyboardButton(text="Past Simple", callback_data="active_past_simple"),
         InlineKeyboardButton(text="Past Continuous", callback_data="active_past_continuous"),
         InlineKeyboardButton(text="Past Perfect", callback_data="active_past_perfect"),
         InlineKeyboardButton(text="Past Perfect Continuous", callback_data="active_past_perfect_continuous"),
         ],
        [InlineKeyboardButton(text="Future Simple", callback_data="active_future_simple"),
         InlineKeyboardButton(text="Future Continuous", callback_data="active_future_continuous"),
         InlineKeyboardButton(text="Future Perfect", callback_data="active_future_perfect"),
         InlineKeyboardButton(text="Future Perfect Continuous", callback_data="active_future_perfect_continuous"),
         ],
        [InlineKeyboardButton(text="Future in the Past Simple", callback_data="active_future_in_the_past_simple"),
         InlineKeyboardButton(text="Future in the Past Continuous", callback_data="active_future_in_the_past_continuous"),
         InlineKeyboardButton(text="Future in the Past Perfect", callback_data="active_future_in_the_past_perfect"),
         InlineKeyboardButton(text="Future in the Past Perfect Continuous",
                              callback_data="active_future_in_the_past_perfect_continuous"),
         ]
    ])

    await callback_query.message.answer("Выберите время:", reply_markup=kb)


@grammar_router.callback_query(F.data == "active_present_simple")
async def handle_active_present_simple(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"handle_present_simple {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Present Simple'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_present_continuous")
async def handle_active_present_continuous(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_present_continuous {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Present Continuous'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_present_perfect")
async def handle_active_present_perfect(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_present_perfect {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Present Perfect'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_present_perfect_continuous")
async def handle_active_present_perfect_continuous(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_present_perfect_continuous {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Present Perfect Continuous'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_past_simple")
async def handle_active_past_simple(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_past_simple {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Past Simple'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_past_continuous")
async def handle_active_past_continuous(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_past_continuous {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Past Continuous'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_past_perfect")
async def handle_active_past_perfect(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_past_perfect {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Past Perfect'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_past_perfect_continuous")
async def handle_active_past_perfect_continuous(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_past_perfect_continuous {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Past Perfect Continuous'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_future_simple")
async def handle_active_future_simple(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_future_simple {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Future Simple'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_future_continuous")
async def handle_active_future_continuous(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_future_continuous {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Future Continuous'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_future_perfect")
async def handle_active_future_perfect(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_future_perfect {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Future Perfect'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_future_perfect_continuous")
async def handle_active_future_perfect_continuous(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_future_perfect_continuous {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Future Perfect Continuous'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_future_in_the_past_simple")
async def handle_active_future_in_the_past_simple(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_future_in_the_past_simple {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Future in the Past Simple'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_future_in_the_past_continuous")
async def handle_active_future_in_the_past_continuous(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_future_in_the_past_continuous {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Future in the Past Continuous'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_future_in_the_past_perfect")
async def handle_active_future_in_the_past_perfect(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_future_in_the_past_perfect {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Future in the Past Perfect'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "active_future_in_the_past_perfect_continuous")
async def handle_active_future_in_the_past_perfect_continuous(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"active_future_in_the_past_perfect_continuous {callback_query.from_user.id}")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM times WHERE time_name = 'Future in the Past Perfect Continuous'")
        result = cursor.fetchone()
        if result:
            # Формируем сообщение с данными
            message = (
                f"<b>Время: {result[0]}</b> (<b>{result[1]}</b>)\n"  # translation_name
                f"<b>Описание:</b> {result[2]}\n\n"  # description
                f"<b>[ + ]:</b> {result[3]}\n"  # formula
                f"<b>     Пример:</b> {result[4]}\n"  # example
                f"<b>     Перевод:</b> {result[5]}\n\n"  # translation_example
                f"<b>[ - ]:</b> {result[6]}\n"  # negative_formula
                f"<b>     Пример:</b> {result[7]}\n"  # example_negative
                f"<b>     Перевод:</b> {result[8]}\n\n"  # translation_example_negative
                f"<b>[ ? ]:</b> {result[9]}\n"  # interrogative_formula
                f"<b>     Пример:</b> {result[10]}\n"  # example_interrogative
                f"<b>     Перевод:</b> {result[11]}"  # translation_example_interrogative
            )
            await callback_query.message.answer(message, parse_mode='HTML')
        else:
            await callback_query.message.answer("Данные не найдены.")

@grammar_router.callback_query(F.data == "select_passive_voice")
async def handle_passive_voice(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"handle_passive_voice {callback_query.from_user.id}")

    # kb = InlineKeyboardMarkup(inline_keyboard=[
    #     [InlineKeyboardButton(text="Present Simple", callback_data="present_simple"),
    #      InlineKeyboardButton(text="Present Continuous", callback_data="present_continuous"),
    #      InlineKeyboardButton(text="Present Perfect", callback_data="present_perfect"),
    #      InlineKeyboardButton(text="Present Perfect Continuous", callback_data="present_perfect_continuous"),
    #      ],
    #     [InlineKeyboardButton(text="Past Simple", callback_data="past_simple"),
    #      InlineKeyboardButton(text="Past Continuous", callback_data="past_continuous"),
    #      InlineKeyboardButton(text="Past Perfect", callback_data="past_perfect"),
    #      InlineKeyboardButton(text="Past Perfect Continuous", callback_data="past_perfect_continuous"),
    #      ],
    #     [InlineKeyboardButton(text="Future Simple", callback_data="future_simple"),
    #      InlineKeyboardButton(text="Future Continuous", callback_data="future_continuous"),
    #      InlineKeyboardButton(text="Future Perfect", callback_data="future_perfect"),
    #      InlineKeyboardButton(text="Future Perfect Continuous", callback_data="future_perfect_continuous"),
    #      ],
    #     [InlineKeyboardButton(text="Future in the Past Simple", callback_data="future_in_the_past_simple"),
    #      InlineKeyboardButton(text="Future in the Past Continuous", callback_data="future_in_the_past_continuous"),
    #      InlineKeyboardButton(text="Future in the Past Perfect", callback_data="future_in_the_past_perfect"),
    #      InlineKeyboardButton(text="Future in the Past Perfect Continuous",
    #                           callback_data="future_in_the_past_perfect_continuous"),
    #      ]
    # ])
    #
    # await callback_query.message.answer("Выберите время:", reply_markup=kb)
    await callback_query.message.answer("В процессе разработки.")