import sqlite3

def initialize_database():
    conn = sqlite3.connect('quiz.db', check_same_thread=False)
    cursor = conn.cursor()

    # Очистка таблиц перед заполнением
    cursor.execute("DELETE FROM questions")
    cursor.execute("DELETE FROM quizzes")

    # Создание таблицы quizzes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE
    )
    ''')

    # Проверка на существование столбца quiz_id в таблице questions
    cursor.execute("PRAGMA table_info(questions)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'quiz_id' not in columns:
        cursor.execute("DROP TABLE IF EXISTS questions")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            quiz_id INTEGER,
            question TEXT UNIQUE,
            answer TEXT,
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
            ('Какое растение вырастает самым высоким?', 'Американская секвоя'),
            ('Какое растение сбрасывает иголки на зиму?', 'Пихта'),
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
