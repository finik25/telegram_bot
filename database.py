import sqlite3

def initialize_database():
    conn = sqlite3.connect('quiz.db', check_same_thread=False)
    cursor = conn.cursor()

    # Проверка на существование таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quizzes'")
    quizzes_table_exists = cursor.fetchone()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'")
    questions_table_exists = cursor.fetchone()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scores'")
    scores_table_exists = cursor.fetchone()

    if not quizzes_table_exists:
        # Создание таблицы quizzes
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE
        )
        ''')

    if not questions_table_exists:
        # Создание таблицы questions
        cursor.execute('''
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
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            quiz_id INTEGER,
            score REAL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
        )
        ''')

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
            ('Какое растение вырастает самым высоким?', 'Американская секвойя'),
            ('Какое растение сбрасывает иголки на зиму?', 'Лиственница'),
            ('Какое растение является хищником?', 'Росянка'),
            ('Какое растение является символом Канады?', 'Клён'),
            ('Какое растение изображалось на гербе королевской Франции?','Лилия')
        ])
    ]

    # Заполнение базы данных
    for quiz_name, questions in quizzes:
        cursor.execute("SELECT id FROM quizzes WHERE name = ?", (quiz_name,))
        quiz_id = cursor.fetchone()
        if not quiz_id:
            cursor.execute("INSERT INTO quizzes (name) VALUES (?)", (quiz_name,))
            quiz_id = cursor.lastrowid
        else:
            quiz_id = quiz_id[0]
        for question, answer in questions:
            cursor.execute("SELECT id FROM questions WHERE question = ?", (question,))
            question_id = cursor.fetchone()
            if not question_id:
                cursor.execute("INSERT INTO questions (quiz_id, question, answer) VALUES (?, ?, ?)",
                               (quiz_id, question, answer))
    conn.commit()
    conn.close()

    return "База данных успешно заполнена данными."

def clear_leaderboard():
    conn = sqlite3.connect('quiz.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scores")
    conn.commit()
    conn.close()
    return "Лидерборд успешно очищен."
