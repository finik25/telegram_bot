import aiosqlite
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name):
        """
        Инициализация базы данных.
        :param db_name: Имя базы данных.
        """
        self.db_name = db_name

    async def initialize_database(self):
        """
        Инициализация базы данных. Создает таблицы, если они не существуют, и заполняет их начальными данными.
        :return: Сообщение об успешной инициализации.
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("PRAGMA foreign_keys = ON")
                cursor = await db.cursor()

                # Проверка на существование таблиц
                await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quizzes'")
                quizzes_table_exists = await cursor.fetchone()

                await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'")
                questions_table_exists = await cursor.fetchone()

                await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scores'")
                scores_table_exists = await cursor.fetchone()

                if not quizzes_table_exists:
                    # Создание таблицы quizzes
                    await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS quizzes (
                        id INTEGER PRIMARY KEY,
                        name TEXT UNIQUE
                    )
                    ''')

                if not questions_table_exists:
                    # Создание таблицы questions
                    await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS questions (
                        id INTEGER PRIMARY KEY,
                        quiz_id INTEGER,
                        question TEXT UNIQUE,
                        answer TEXT,
                        FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
                    )
                    ''')

                if not scores_table_exists:
                    # Создание таблицы scores
                    await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS scores (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        username TEXT,
                        quiz_id INTEGER,
                        score REAL,
                        FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
                    )
                    ''')

                # Добавление базовых викторин и вопросов в базу данных
                quizzes = [
                    ('Столицы стран', [
                        ('Столица Франции?', 'Париж'),
                        ('Столица Исландии?', 'Рейкьявик'),
                        ('Столица Германии?', 'Берлин'),
                        ('Столица Испании?', 'Мадрид'),
                        ('Столица Белоруссии?', 'Минск'),
                        ('Столица Италии?', 'Рим')
                    ]),
                    ('Животные', [
                        ('Самое крупное животное на суше - это?', 'Слон'),
                        ('Самое медленное животное - это?', 'Ленивец'),
                        ('Самое крупное морское животное - это?', 'Кит'),
                        ('Самое быстрое животное на суше - это?', 'Гепард')
                    ]),
                    ('Растения', [
                        ('Какое растение вырастает самым высоким?', 'Секвойя'),
                        ('Какое растение является символом Канады?', 'Клён'),
                        ('Какое растение сбрасывает иголки на зиму?', 'Лиственница'),
                        ('Какое дерево считается символом России?', 'Берёза'),
                        ('Какой цветок изображался на гербе королевской Франции?', 'Лилия'),
                        ('Какое растение является хищником?', 'Росянка')
                    ])
                ]

                # Заполнение базы данных
                for quiz_name, questions in quizzes:
                    await cursor.execute("SELECT id FROM quizzes WHERE name = ?", (quiz_name,))
                    quiz_id = await cursor.fetchone()
                    if not quiz_id:
                        await cursor.execute("INSERT INTO quizzes (name) VALUES (?)", (quiz_name,))
                        quiz_id = cursor.lastrowid
                    else:
                        quiz_id = quiz_id[0]
                    for question, answer in questions:
                        await cursor.execute("SELECT id FROM questions WHERE question = ?", (question,))
                        question_id = await cursor.fetchone()
                        if not question_id:
                            await cursor.execute("INSERT INTO questions (quiz_id, question, answer) VALUES (?, ?, ?)",
                                                   (quiz_id, question, answer))
                await db.commit()

            return "База данных успешно заполнена данными."
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            return "Ошибка при инициализации базы данных."

    async def clear_leaderboard(self):
        """
        Очистка лидерборда. Удаляет все записи из таблицы scores.
        :return: Сообщение об успешной очистке.
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("DELETE FROM scores")
                await db.commit()
            return "Лидерборд успешно очищен."
        except Exception as e:
            logger.error(f"Error clearing leaderboard: {e}")
            return "Ошибка при очистке лидерборда."

    async def add_quiz(self, quiz_name, questions):
        """
        Добавление новой викторины.
        :param quiz_name: Название викторины.
        :param questions: Список вопросов и ответов.
        :return: Сообщение об успешном добавлении.
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.cursor()
                await db.execute("BEGIN")
                try:
                    await cursor.execute("INSERT INTO quizzes (name) VALUES (?)", (quiz_name,))
                    quiz_id = cursor.lastrowid
                    for question, answer in questions:
                        await cursor.execute("SELECT id FROM questions WHERE question = ?", (question,))
                        question_id = await cursor.fetchone()
                        if not question_id:
                            await cursor.execute("INSERT INTO questions (quiz_id, question, answer) VALUES (?, ?, ?)",
                                                 (quiz_id, question, answer))
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    raise e
            return f"Викторина '{quiz_name}' успешно добавлена."
        except Exception as e:
            logger.error(f"Error adding quiz: {e}")
            return f"Ошибка при добавлении викторины '{quiz_name}'."

    async def update_quiz(self, quiz_name, new_quiz_name, questions):
        """
        Обновление существующей викторины.
        :param quiz_name: Текущее название викторины.
        :param new_quiz_name: Новое название викторины.
        :param questions: Список новых вопросов и ответов.
        :return: Сообщение об успешном обновлении.
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.cursor()
                await db.execute("BEGIN")
                try:
                    await cursor.execute("UPDATE quizzes SET name = ? WHERE name = ?", (new_quiz_name, quiz_name))
                    await cursor.execute("SELECT id FROM quizzes WHERE name = ?", (new_quiz_name,))
                    quiz_id = await cursor.fetchone()
                    if quiz_id:
                        quiz_id = quiz_id[0]
                        await cursor.execute("DELETE FROM questions WHERE quiz_id = ?", (quiz_id,))
                        for question, answer in questions:
                            await cursor.execute("INSERT INTO questions (quiz_id, question, answer) VALUES (?, ?, ?)",
                                                 (quiz_id, question, answer))
                        await db.commit()
                    else:
                        await db.rollback()
                        return f"Викторина '{quiz_name}' не найдена."
                except Exception as e:
                    await db.rollback()
                    raise e
            return f"Викторина '{quiz_name}' успешно обновлена на '{new_quiz_name}'."
        except Exception as e:
            logger.error(f"Error updating quiz: {e}")
            return f"Ошибка при обновлении викторины '{quiz_name}'."

    async def delete_quiz(self, quiz_name):
        """
        Удаление викторины по названию.
        :param quiz_name: Название викторины.
        :return: Сообщение об успешном удалении.
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.cursor()
                await db.execute("BEGIN")
                try:
                    await cursor.execute("SELECT id FROM quizzes WHERE name = ?", (quiz_name,))
                    quiz_id = await cursor.fetchone()
                    if quiz_id:
                        quiz_id = quiz_id[0]
                        await cursor.execute("DELETE FROM questions WHERE quiz_id = ?", (quiz_id,))
                        await cursor.execute("DELETE FROM quizzes WHERE name = ?", (quiz_name,))
                        await db.commit()
                    else:
                        await db.rollback()
                        return f"Викторина '{quiz_name}' не найдена."
                except Exception as e:
                    await db.rollback()
                    raise e
            return f"Викторина '{quiz_name}' успешно удалена."
        except Exception as e:
            logger.error(f"Error deleting quiz: {e}")
            return f"Ошибка при удалении викторины '{quiz_name}'."

    async def delete_quiz_by_id(self, quiz_id):
        """
        Удаление викторины по ID.
        :param quiz_id: ID викторины.
        :return: Сообщение об успешном удалении.
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.cursor()
                await db.execute("BEGIN")
                try:
                    # Получаем название викторины по её ID
                    await cursor.execute("SELECT name FROM quizzes WHERE id = ?", (quiz_id,))
                    quiz_name = await cursor.fetchone()
                    quiz_name = quiz_name[0] if quiz_name else "Unknown Quiz"

                    await cursor.execute("DELETE FROM questions WHERE quiz_id = ?", (quiz_id,))
                    await cursor.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
                    await db.commit()
                    return f"Викторина '{quiz_name}' успешно удалена."
                except Exception as e:
                    await db.rollback()
                    raise e
        except Exception as e:
            logger.error(f"Error deleting quiz by ID: {e}")
            return f"Ошибка при удалении викторины с ID {quiz_id}."

    async def get_quizzes(self):
        """
        Получение списка всех викторин.
        :return: Список викторин.
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT id, name FROM quizzes")
                return await cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting quizzes: {e}")
            return []

    async def get_quiz_details(self, quiz_id):
        """
        Получение деталей викторины по её ID.
        :param quiz_id: ID викторины.
        :return: Название викторины и список вопросов.
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT name FROM quizzes WHERE id = ?", (quiz_id,))
                quiz_name = await cursor.fetchone()
                await cursor.execute("SELECT question, answer FROM questions WHERE quiz_id = ?", (quiz_id,))
                questions = await cursor.fetchall()
                return quiz_name[0], questions
        except Exception as e:
            logger.error(f"Error getting quiz details: {e}")
            return None, []
