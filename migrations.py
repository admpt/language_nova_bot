import sqlite3
from sqlite3 import Connection

def upgrade_to_v1(conn: Connection) -> None:
    """Обновление базы данных до версии 1"""
    cursor = conn.cursor()

    # Проверяем существование таблицы `users`
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    table_exists = cursor.fetchone()

    if table_exists:
        # Проверяем существование столбца `full_name` и добавляем, если его нет
        cursor.execute("PRAGMA table_info(users);")
        columns = [column[1] for column in cursor.fetchall()]

        if 'full_name' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN full_name TEXT;")

        # Добавляем столбец `learned_words_count`, если его нет
        if 'learned_words_count' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN learned_words_count INTEGER DEFAULT 0;")

        # Добавляем столбец `topics_count`, если его нет
        if 'topics_count' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN topics_count INTEGER DEFAULT 0;")

        if 'referral_code' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN referral_code TEXT;")

            # Добавляем столбец `referred_by`, если его нет
        if 'referred_by' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER;")

            # Добавляем столбец `elite_start_date`, если его нет
        if 'elite_start_date' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN elite_start_date DATETIME;")

            # Добавляем столбец `elite_status`, если его нет
        if 'elite_status' not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN elite_status TEXT DEFAULT 'No' CHECK(elite_status IN ('Yes', 'No'));")


    else:

        # Если таблицы нет, создаем её

        cursor.execute(""" 
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username_tg TEXT,
                    full_name TEXT,
                    balance INTEGER DEFAULT 0,
                    elite_status TEXT DEFAULT 'No' CHECK(elite_status IN ('Yes', 'No')),
                    learned_words_count INTEGER DEFAULT 0,
                    referral_code TEXT,
                    referred_by INTEGER,
                    elite_start_date DATETIME
                )
            """)

    # Создаем таблицу `user_dictionary`
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_dictionary';")
    table_exists = cursor.fetchone()

    if not table_exists:
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS user_dictionary (
                user_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                translation TEXT NOT NULL,
                PRIMARY KEY (user_id, topic_id, word),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

    # Создаем таблицу `topics`
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='topics';")
    table_exists = cursor.fetchone()

    if not table_exists:
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                visible INTEGER DEFAULT 0 CHECK(visible IN (0, 1)),
                FOREIGN KEY (author_id) REFERENCES users (user_id)
            )
        """)

    # Создаем таблицу `irregular_verbs`
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='irregular_verbs';")
    table_exists = cursor.fetchone()

    if table_exists:
        cursor.execute("PRAGMA table_info(irregular_verbs);")
        columns = [column[1] for column in cursor.fetchall()]

        if 'v1_second' not in columns:  # Проверяем, существует ли столбец
            cursor.execute("ALTER TABLE irregular_verbs ADD COLUMN v1_second TEXT DEFAULT NULL;")

    if not table_exists:
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS irregular_verbs (
                v1 TEXT NOT NULL,
                v2_first TEXT NOT NULL,
                v2_second TEXT DEFAULT NULL,
                v3_first TEXT NOT NULL,
                v3_second TEXT DEFAULT NULL,
                first_translation TEXT NOT NULL,
                second_translation TEXT DEFAULT NULL,
                third_translation TEXT DEFAULT NULL
            )
        """)

    # Создаем таблицу `times`
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='times';")
    table_exists = cursor.fetchone()

    if not table_exists:
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS times (
                time_name TEXT NOT NULL,
                translation_name TEXT NOT NULL,
                description TEXT NOT NULL,
                formula TEXT NOT NULL,
                example TEXT NOT NULL,
                translation_example TEXT NOT NULL,
                negative_formula TEXT NOT NULL,
                example_negative TEXT NOT NULL,
                translation_example_negative TEXT NOT NULL,
                interrogative_formula TEXT NOT NULL,
                example_interrogative TEXT NOT NULL,
                translation_example_interrogative TEXT NOT NULL
            )
        """)

    conn.commit()


def migrate(db_file: str) -> None:
    """Функция для применения миграций"""
    conn = sqlite3.connect(db_file)
    try:
        upgrade_to_v1(conn)  # Применяем миграцию версии 1
        print("Migration applied.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate('database.db')
