import aiosqlite

class Database:
    def __init__(self, db_name):
        self.db_name = db_name

    async def initialize_database(self):
        async with aiosqlite.connect(self.db_name) as db:
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

            # Удаление всех данных из таблицы questions
            await cursor.execute("DELETE FROM questions")

            # Добавление викторин и вопросов в базу данных
            quizzes = [
                ('Столицы стран', [
                    ('Столица Франции?', 'Париж'),
                    ('Столица Германии?', 'Берлин'),
                    ('Столица Белоруссии?', 'Минск'),
                    ('Столица Исландии','Рейкьявик')
                ]),
                ('Животные', [
                    ('Самое крупное животное на суше - это?', 'Слон'),
                    ('Самое быстрое животное на суше - это?', 'Гепард')
                ]),
                ('Растения', [
                    ('Какое растение вырастает самым высоким?', 'Секвойя'),
                    ('Какое растение сбрасывает иголки на зиму?', 'Лиственница'),
                    ('Какое растение является хищником?', 'Росянка'),
                    ('Какое растение является символом Канады?', 'Клён'),
                    ('Какое растение изображалось на гербе королевской Франции?','Лилия')
                ])
            ]

            # Заполнение базы данных
            for quiz_name, questions in quizzes:
                await cursor.execute("SELECT id FROM quizzes WHERE name = ?", (quiz_name,))
                quiz_id = await cursor.fetchone()
                if not quiz_id:
                    await cursor.execute("INSERT INTO quizzes (name) VALUES (?)", (quiz_name,))
                    quiz_id = await cursor.lastrowid
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

    async def clear_leaderboard(self):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.cursor()
            await cursor.execute("DELETE FROM scores")
            await db.commit()
        return "Лидерборд успешно очищен."