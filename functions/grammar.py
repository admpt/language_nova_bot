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
        [InlineKeyboardButton(text="Повторять", callback_data="start_repeat_irregular_verbs")]
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


@grammar_router.callback_query(F.data == "start_repeat_irregular_verbs")
async def start_repeat_irregular_verbs(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"start_repeat_irregular_verbs {callback_query.from_user.id}")
    await state.clear()
    user_id = callback_query.from_user.id
    await state.set_state(TranslationStates.repeat_irregular_verbs)
    await ask_for_irregular_repeat(callback_query.message, user_id, state)

@grammar_router.message(F.text=='ask_for_irregular_repeat')
async def ask_for_irregular_repeat(message: types.Message, user_id: int, state: FSMContext):
    logging.info(f"ask_for_irregular_repeat {message.from_user.id}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    stop_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Прекратить повтор")]],
        resize_keyboard=True
    )

    try:
        cursor.execute(
            "SELECT v1, v1_second, v2_first, v2_second, v3_first, v3_second, first_translation, second_translation, third_translation FROM irregular_verbs")
        verbs = cursor.fetchall()

        if verbs:
            verb_data = random.choice(verbs)  # Выбираем случайный глагол
            v1, v1_second, v2_first, v2_second, v3_first, v3_second, *translations = verb_data

            # Удаляем None из списков
            translations = [t for t in translations if t]  # Убираем пустые строки

            # Сохраняем данные о текущем глаголе
            await state.update_data(
                current_verb=v1,
                v1_second=v1_second,
                v2_first=v2_first,
                v2_second=v2_second,
                v3_first=v3_first,
                v3_second=v3_second,
                translations=translations
            )

            # Случайным образом выбираем форму для повторения
            form_choice = random.choice(["Infinitive", "Past Simple", "Past Participle"])
            await state.update_data(form_choice=form_choice)

            # Отправляем вопрос пользователю
            await message.answer(f"Введите {form_choice} для: {', '.join(filter(None, translations))}",
                                 reply_markup=stop_kb)

        else:
            await message.answer("В базе данных нет глаголов.", reply_markup=stop_kb)
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await message.answer("Произошла ошибка при получении глаголов.", reply_markup=stop_kb)
    finally:
        conn.close()


@grammar_router.message(lambda message: message.text.strip() != "Прекратить повтор", TranslationStates.repeat_irregular_verbs)
async def check_repeat_answer(message: types.Message, state: FSMContext):
    logging.info(f"check_repeat_answer {message.from_user.id}")
    # Получаем текущее состояние
    current_state = await state.get_state()

    # Если состояние сброшено (None), игнорируем сообщение
    if current_state is None:
        return

    data = await state.get_data()
    current_verb = data.get("current_verb")
    v1_second = data.get("v1_second")
    v2_first = data.get("v2_first")
    v2_second = data.get("v2_second")
    v3_first = data.get("v3_first")
    v3_second = data.get("v3_second")
    form_choice = data.get("form_choice")

    user_input = message.text.strip()

    # Проверяем правильный ответ в зависимости от формы
    if form_choice == "Infinitive":
        if user_input in [current_verb, v1_second]:
            await message.answer("Правильно!")
        else:
            await message.answer(f"Неправильно. Правильный ответ: {current_verb}.")

    elif form_choice == "Past Simple":
        if user_input in [v2_first, v2_second]:
            await message.answer("Правильно!")
        else:
            await message.answer(f"Неправильно. Правильный ответ: {v2_first} или {v2_second}.")

    elif form_choice == "Past Participle":
        if user_input in [v3_first, v3_second]:
            await message.answer("Правильно!")
        else:
            await message.answer(f"Неправильно. Правильный ответ: {v3_first} или {v3_second}.")

    # Запрашиваем следующее слово
    await ask_for_irregular_repeat(message, message.from_user.id, state)


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
        [InlineKeyboardButton(text="Present Simple", callback_data="present_simple"),
         InlineKeyboardButton(text="Present Continuous", callback_data="present_continuous"),
         InlineKeyboardButton(text="Present Perfect", callback_data="present_perfect"),
         InlineKeyboardButton(text="Present Perfect Continuous", callback_data="present_perfect_continuous"),
         ],
        [InlineKeyboardButton(text="Past Simple", callback_data="past_simple"),
         InlineKeyboardButton(text="Past Continuous", callback_data="past_continuous"),
         InlineKeyboardButton(text="Past Perfect", callback_data="past_perfect"),
         InlineKeyboardButton(text="Past Perfect Continuous", callback_data="past_perfect_continuous"),
         ],
        [InlineKeyboardButton(text="Future Simple", callback_data="future_simple"),
         InlineKeyboardButton(text="Future Continuous", callback_data="future_continuous"),
         InlineKeyboardButton(text="Future Perfect", callback_data="future_perfect"),
         InlineKeyboardButton(text="Future Perfect Continuous", callback_data="future_perfect_continuous"),
         ],
        [InlineKeyboardButton(text="Future in the Past Simple", callback_data="future_in_the_past_simple"),
         InlineKeyboardButton(text="Future in the Past Continuous", callback_data="future_in_the_past_continuous"),
         InlineKeyboardButton(text="Future in the Past Perfect", callback_data="future_in_the_past_perfect"),
         InlineKeyboardButton(text="Future in the Past Perfect Continuous",
                              callback_data="future_in_the_past_perfect_continuous"),
         ]
    ])

    await callback_query.message.answer("Выберите время:", reply_markup=kb)


@grammar_router.callback_query(F.data == "select_passive_voice")
async def handle_passive_voice(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"handle_passive_voice {callback_query.from_user.id}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Present Simple", callback_data="present_simple"),
         InlineKeyboardButton(text="Present Continuous", callback_data="present_continuous"),
         InlineKeyboardButton(text="Present Perfect", callback_data="present_perfect"),
         InlineKeyboardButton(text="Present Perfect Continuous", callback_data="present_perfect_continuous"),
         ],
        [InlineKeyboardButton(text="Past Simple", callback_data="past_simple"),
         InlineKeyboardButton(text="Past Continuous", callback_data="past_continuous"),
         InlineKeyboardButton(text="Past Perfect", callback_data="past_perfect"),
         InlineKeyboardButton(text="Past Perfect Continuous", callback_data="past_perfect_continuous"),
         ],
        [InlineKeyboardButton(text="Future Simple", callback_data="future_simple"),
         InlineKeyboardButton(text="Future Continuous", callback_data="future_continuous"),
         InlineKeyboardButton(text="Future Perfect", callback_data="future_perfect"),
         InlineKeyboardButton(text="Future Perfect Continuous", callback_data="future_perfect_continuous"),
         ],
        [InlineKeyboardButton(text="Future in the Past Simple", callback_data="future_in_the_past_simple"),
         InlineKeyboardButton(text="Future in the Past Continuous", callback_data="future_in_the_past_continuous"),
         InlineKeyboardButton(text="Future in the Past Perfect", callback_data="future_in_the_past_perfect"),
         InlineKeyboardButton(text="Future in the Past Perfect Continuous",
                              callback_data="future_in_the_past_perfect_continuous"),
         ]
    ])

    await callback_query.message.answer("Выберите время:", reply_markup=kb)