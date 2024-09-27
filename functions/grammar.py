import logging
import sqlite3
from uuid import uuid4

from aiogram import types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from main import dp, DB_FILE, TOKEN
bot = Bot(token=TOKEN)

logging.basicConfig(level=logging.INFO)


# Обработчик сообщения "Грамматика"
@dp.message(F.text=="Грамматика")
async def grammar(message: types.Message, state: FSMContext) -> None:
    await state.clear()  # Сбрасываем состояние
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Irregular Verbs", callback_data='irregular_verbs')]
    ])
    await message.answer("Выберите тему по грамматике:", reply_markup=kb)


# Обработчик callback запроса для "Irregular Verbs"
@dp.callback_query(F.data == "irregular_verbs")
async def handle_irregular_verbs(callback_query: types.CallbackQuery, state: FSMContext):
    command = "введите глагол в форме Infinitive: "  # Определяем команду
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Неправильные глаголы", switch_inline_query_current_chat=command)]
    ])
    await callback_query.message.answer(
        "Вы выбрали тему: Неправильные глаголы.\nПожалуйста, введите глагол в форме инфинитива:",
        reply_markup=kb
    )
    await callback_query.answer()  # Подтверждаем callback


# Обработчик инлайн-запроса
@dp.inline_query(lambda query: query.query.startswith("введите глагол в форме Infinitive: "))
async def inline_query_handler_irregular(inline_query: types.InlineQuery) -> None:
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
@dp.message(lambda message: message.text.startswith("Глагол: "))
async def process_topic_selection_repeat(message: types.Message, state: FSMContext) -> None:
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