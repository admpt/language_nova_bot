import logging
import sqlite3
from sqlite3 import Connection

from aiogram import F, types, Bot, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent

from functions.start_command import get_user_id_by_referral_code
from shared import is_command, update_learned_words_count, update_learned_topics_count, TOKEN
from shared import DB_FILE, Form, create_connection
from token_of_bot import API_TOKEN

from aiogram.client.session.aiohttp import AiohttpSession

session = AiohttpSession(proxy="http://proxy.server:3128")
bot = Bot(token=TOKEN, session=session)

add_words_router = Router()
global topic_id

# Функция для поиска тем пользователя
async def search_user_topics(user_id: int, query: str) -> list:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()

        cursor.execute("""SELECT id, content 
                          FROM topics 
                          WHERE (author_id = ? OR visible = 1) 
                          AND content LIKE ?""", (user_id, f"%{query}%"))

        results = cursor.fetchall()

        # Логируем результаты поиска
        logging.info(f"Found topics: {results}")

        return results
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return []
    finally:
        conn.close()

# Обработка команды "Добавить слова"
@add_words_router.message(F.text == "Добавить слова", StateFilter(None))
async def add_words_prompt(message: types.Message, state: FSMContext) -> None:
    logging.info(f"add_words_prompt {message.from_user.id}")
    await state.clear()  # Сбрасываем состояние
    command = "поиск темы для добавления слов: "
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать тему", switch_inline_query_current_chat=command)]
    ])
    await message.answer("Выберите тему из предложенных:", reply_markup=kb)


@add_words_router.inline_query(F.query.startswith("поиск темы для добавления слов: "))
async def inline_query_handler(inline_query: types.InlineQuery) -> None:
    logging.info(f"inline_query_handler {inline_query.from_user.id}")
    query = inline_query.query[len("поиск темы для добавления слов: "):].strip()  # Убираем команду
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
                    message_text=f"Вы выбрали тему: {item[1]}"
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


@add_words_router.message(lambda message: message.text.startswith("Вы выбрали тему:"), StateFilter(None))
async def process_topic_selection(message: types.Message, state: FSMContext) -> None:
    global topic_id
    logging.info(f"process_topic_selection {message.from_user.id}")
    topic_name = message.text.split(": ", 1)[-1]

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Получаем ID темы и её детали
        cursor.execute("SELECT id, visible, author_id FROM topics WHERE content = ?", (topic_name,))
        topic = cursor.fetchone()

        if topic:
            topic_id, is_visible, author_id = topic
            cursor.execute("SELECT COUNT(*) FROM user_dictionary WHERE topic_id = ?", (topic_id,))
            word_count = cursor.fetchone()[0]

            # Получаем информацию об авторе
            cursor.execute("SELECT full_name FROM users WHERE user_id = ?", (author_id,))
            author = cursor.fetchone()
            author_name = author[0] if author else "Неизвестный автор"
            author_link = f"[{author_name}](tg://user?id={author_id})"

            message_text = (f"Название темы: *{topic_name}*\n"
                            f"Количество слов: {word_count}\n"
                            # f"Статус: {'Публичная' if is_visible else 'Приватная'}\n"
                            f"Автор: {author_link}")

            # Создаём клавиатуру с действиями
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Добавить слово", callback_data=f"add_words:{topic_id}"),
                 InlineKeyboardButton(text="Удалить тему", callback_data=f"delete_topic:{topic_id}")],
                [InlineKeyboardButton(text="Слова в теме", callback_data=f"show_words:{topic_id}")],
                # [InlineKeyboardButton(text="Сделать приватной" if is_visible else "Сделать публичной",
                #                       callback_data=f"toggle_visibility:{topic_id}")]
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


# @add_words_router.callback_query(F.data.startswith("toggle_visibility:"))
# async def toggle_visibility(callback_query: types.CallbackQuery) -> None:
#     global topic_id
#     topic_id = int(callback_query.data.split(":")[1])
#
#     conn = sqlite3.connect(DB_FILE)
#     cursor = conn.cursor()
#
#     try:
#         cursor.execute("SELECT visible, author_id FROM topics WHERE id = ?", (topic_id,))
#         result = cursor.fetchone()
#
#         if result:
#             current_visibility, author_id = result
#             new_visibility = 1 - current_visibility  # Меняем статус
#
#             # Обновляем статус в базе данных
#             cursor.execute("UPDATE topics SET visible = ? WHERE id = ?", (new_visibility, topic_id))
#             conn.commit()
#
#             # Получаем новое название темы и количество слов
#             cursor.execute("SELECT content FROM topics WHERE id = ?", (topic_id,))
#             topic_name = cursor.fetchone()[0]
#
#             cursor.execute("SELECT COUNT(*) FROM user_dictionary WHERE topic_id = ?", (topic_id,))
#             word_count = cursor.fetchone()[0]
#
#             # Получаем информацию об авторе
#             cursor.execute("SELECT full_name FROM users WHERE user_id = ?", (author_id,))
#             author = cursor.fetchone()
#             author_username = author[0] if author else "Неизвестный автор"
#
#             # Создаем ссылку на профиль автора
#             author_link = f"[{author_username}](tg://user?id={author_id})"
#
#             status_text = "Публичный" if new_visibility else "Приватный"
#             # message_text = f"Название темы: *{topic_name}*\nКоличество слов: {word_count}\nСтатус: {status_text}\nАвтор: {author_link}"
#             message_text = f"Название темы: *{topic_name}*\nКоличество слов: {word_count}\nАвтор: {author_link}"
#             await callback_query.answer(f"Статус темы изменен на {status_text}.", show_alert=True)
#
#             # Создаём новую клавиатуру с обновлённой кнопкой
#             kb = InlineKeyboardMarkup(inline_keyboard=[
#                 [InlineKeyboardButton(text="RU-ENG", callback_data=f"ru_eng:{topic_id}"),
#                  InlineKeyboardButton(text="ENG-RU", callback_data=f"eng_ru:{topic_id}")],
#                 [InlineKeyboardButton(text="Слова в теме", callback_data=f"show_words:{topic_id}")],
#                 [InlineKeyboardButton(text="Сделать приватной" if new_visibility else "Сделать публичной",
#                                      callback_data=f"toggle_visibility:{topic_id}")]
#             ])
#
#             # Обновляем сообщение с новой информацией и клавиатурой
#             await callback_query.message.edit_text(message_text, parse_mode='Markdown', reply_markup=kb)
#         else:
#             await callback_query.answer("Тема не найдена.", show_alert=True)
#     except sqlite3.Error as e:
#         logging.error(f"Database error: {e}")
#         await callback_query.answer("Произошла ошибка при изменении видимости темы.", show_alert=True)
#     finally:
#         conn.close()



# Функция для добавления или обновления пользователя в базе данных
async def upsert_user(user_id: int, username_tg: str, full_name: str, referral_code: str = None,
                      balance: int = 0, elite_status: str = 'No', learned_words_count: int = 0,
                      elite_start_date: str = None) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()

        # Генерация уникального реферального кода
        unique_referral_code = str(user_id)  # Можно изменить на более сложную генерацию

        # Если реферальный код указан, проверяем и обновляем `referred_by`
        referred_by_id = None
        if referral_code:
            referred_by_id = get_user_id_by_referral_code(referral_code)

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
        referred_by_id, elite_start_date))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()




@add_words_router.callback_query(lambda c: c.data.startswith("add_words:"))
async def add_words_callback(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"add_words_callback {callback_query.from_user.id}")
    topic_id = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id

    # Получаем название темы из базы данных
    conn = create_connection(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM topics WHERE id = ?", (topic_id,))
    topic_name = cursor.fetchone()

    if topic_name:
        topic_name = topic_name[0]  # Получаем строку из кортежа

        # Сохраняем ID и название темы в состоянии
        await state.update_data(selected_topic_id=topic_id, selected_topic_name=topic_name)
        await callback_query.message.answer("Введите слово на английском:")
        await state.set_state(Form.waiting_for_word)
    else:
        await callback_query.answer("Тема не найдена.")

# Обработка текста для добавления слова
@add_words_router.message(Form.waiting_for_word)
async def handle_word_input(message: types.Message, state: FSMContext) -> None:
    logging.info(f"handle_word_input {message.from_user.id}")
    word = message.text.strip()
    logging.info(f"Получено слово: {word}")

    if is_command(word):
        await message.answer("Вы не можете использовать названия команд в качестве аргументов.")
        return

    await state.update_data(word_to_add=word)
    await message.answer("Введите перевод слова:")
    await state.set_state(Form.waiting_for_translation)

# Функция для добавления слова в выбранную тему
async def add_word_to_user_topic(user_id: int, topic_id: int, word: str, translation: str) -> None:
    conn = create_connection(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO user_dictionary (user_id, topic_id, word, translation)
                          VALUES (?, ?, ?, ?)""", (user_id, topic_id, word, translation))

        # Обновляем количество изученных слов
        await update_learned_words_count(user_id)

        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        conn.close()

# Обработка текста для добавления перевода
@add_words_router.message(Form.waiting_for_translation)
async def process_translation(message: types.Message, state: FSMContext) -> None:
    logging.info(f"process_translation {message.from_user.id}")
    translation = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    word = data.get('word_to_add')
    topic_id = data.get('selected_topic_id')
    topic_name = data.get('selected_topic_name')  # Получаем название темы

    logging.info(f"Получен перевод: {translation} для слова: {word} в теме '{topic_name}' с ID: {topic_id}")

    if not topic_id:
        await message.answer("Ошибка: не выбрана тема для добавления слова.")
        return

    if is_command(translation):
        await message.answer("Вы не можете использовать названия команд в качестве аргументов.")
        return
    await update_learned_words_count(user_id)
    await add_word_to_user_topic(user_id, topic_id, word, translation)
    await state.clear()  # Очищаем состояние после добавления
    await update_learned_words_count(user_id)
    message_text = f'Слово *"{word}"* с переводом *"{translation}"* успешно добавлено в тему *"{topic_name}"*!'
    await message.answer(message_text, parse_mode='Markdown')


@add_words_router.callback_query(lambda c: c.data.startswith("delete_topic:"))
async def delete_topic_callback(callback_query: types.CallbackQuery):
    logging.info(f"delete_topic_callback {callback_query.from_user.id}")
    topic_id = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id

    # Получаем название темы для подтверждения
    conn = create_connection(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM topics WHERE id = ?", (topic_id,))
    topic = cursor.fetchone()

    if topic:
        topic_name = topic[0]

        # Предлагаем подтвердить удаление
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data=f"confirm_delete:{topic_id}"),
             InlineKeyboardButton(text="Нет", callback_data="cancel_delete")]
        ])
        await callback_query.message.answer(f'Вы уверены, что хотите удалить тему "{topic_name}" и все связанные с ней слова?',
                                    reply_markup=kb)
    else:
        await callback_query.answer("Тема не найдена.")
    conn.close()


@add_words_router.callback_query(lambda c: c.data.startswith("confirm_delete:"))
async def confirm_delete_topic(callback_query: types.CallbackQuery):
    logging.info(f"confirm_delete_topic {callback_query.from_user.id}")
    topic_id = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    conn = create_connection(DB_FILE)
    cursor = conn.cursor()
    await update_learned_words_count(user_id)
    await update_learned_topics_count(user_id)
    try:
        # Удаляем все слова, связанные с темой
        cursor.execute("DELETE FROM user_dictionary WHERE topic_id = ?", (topic_id,))

        # Удаляем тему
        cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        conn.commit()

        await callback_query.message.answer("Тема и все связанные слова успешно удалены.")
        await update_learned_words_count(user_id)
        await update_learned_topics_count(user_id)
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await callback_query.message.answer("Произошла ошибка при удалении темы.")
    finally:
        conn.close()


@add_words_router.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete_topic(callback_query: types.CallbackQuery):
    logging.info(f"cancel_delete_topic {callback_query.from_user.id}")
    await callback_query.message.answer("Удаление темы отменено.")
    user_id = callback_query.from_user.id
    await update_learned_words_count(user_id)
    await update_learned_topics_count(user_id)
