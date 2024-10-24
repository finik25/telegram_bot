import asyncio
import aiosqlite
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from database import initialize_database, clear_leaderboard

API_TOKEN = '8153449820:AAGrGlihbiwy4jTfOhhvzn1KI1Nrj4JQMGE'
bot = AsyncTeleBot(API_TOKEN)

# Блокировка для синхронизации доступа к базе данных
lock = asyncio.Lock()

# Хранилище состояния игры
game_state = {}

# Обработчик команды /start
@bot.message_handler(commands=['start'])
async def send_welcome(message):
    chat_id = message.chat.id
    keyboard = types.InlineKeyboardMarkup()
    single_button = types.InlineKeyboardButton(text="Одиночная", callback_data="single")
    pvp_button = types.InlineKeyboardButton(text="PVP-викторина", callback_data="pvp")
    keyboard.add(single_button, pvp_button)
    await bot.send_message(chat_id, "Привет! Выбери тип викторины:", reply_markup=keyboard)

# Обработчик команды /quiz
@bot.message_handler(commands=['quiz'])
async def start_quiz(message):
    chat_id = message.chat.id
    async with lock:
        async with aiosqlite.connect('quiz.db') as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT id, name FROM quizzes")
            quizzes = await cursor.fetchall()

    if quizzes:
        keyboard = types.InlineKeyboardMarkup()
        for quiz_id, quiz_name in quizzes:
            button = types.InlineKeyboardButton(text=quiz_name, callback_data=f"quiz_{quiz_id}")
            keyboard.add(button)
        await bot.send_message(chat_id, "Выбери викторину:", reply_markup=keyboard)
    else:
        await bot.send_message(chat_id, "Нет доступных викторин.")

# Обработчик команды /leaderboard
@bot.message_handler(commands=['leaderboard'])
async def show_leaderboard(message):
    chat_id = message.chat.id
    async with lock:
        async with aiosqlite.connect('quiz.db') as db:
            cursor = await db.cursor()
            await cursor.execute("""
                SELECT username, quiz_id, score,
                       (SELECT COUNT(*) FROM questions WHERE quiz_id = scores.quiz_id) as total_questions
                FROM scores
                ORDER BY score DESC
            """)
            leaderboard = await cursor.fetchall()

    if leaderboard:
        user_leaderboard = {}
        for username, quiz_id, score, total_questions in leaderboard:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT name FROM quizzes WHERE id = ?", (quiz_id,))
                quiz_name = (await cursor.fetchone())[0]
            if username not in user_leaderboard or score > user_leaderboard[username]['score']:
                user_leaderboard[username] = {
                    'quiz_name': quiz_name,
                    'score': int(score),
                    'total_questions': total_questions
                }

        response = "Лидерборд:\n"
        position = 1
        for username, data in user_leaderboard.items():
            response += f"{position}. {username} - {data['quiz_name']}: {data['score']}/{data['total_questions']} ({data['score']/data['total_questions']*100:.2f}%)\n"
            position += 1
        await bot.send_message(chat_id, response)
    else:
        await bot.send_message(chat_id, "Лидерборд пока пуст.")

# Обработчик команды /clear_leaderboard
@bot.message_handler(commands=['clear_leaderboard'])
async def clear_leaderboard_command(message):
    chat_id = message.chat.id
    await clear_leaderboard()
    await bot.send_message(chat_id, "Лидерборд успешно очищен.")

# Обработчик callback-запросов
@bot.callback_query_handler(func=lambda call: True)
async def handle_quiz_selection(call):
    chat_id = call.message.chat.id
    if call.data == "single":
        await start_quiz(call.message)
    elif call.data == "pvp":
        await bot.send_message(chat_id, "Функция PVP-викторины пока недоступна.")
    elif call.data == "newquiz":
        await start_quiz(call.message)
    else:
        try:
            action, quiz_id = call.data.split('_')
        except ValueError:
            return

        if action == "quiz":
            quiz_id = int(quiz_id)
            print(f"Callback data received: {call.data}")  # Логирование для отладки
            async with lock:
                async with aiosqlite.connect('quiz.db') as db:
                    cursor = await db.cursor()
                    await cursor.execute("SELECT question, answer FROM questions WHERE quiz_id = ? ORDER BY RANDOM()", (quiz_id,))
                    questions = await cursor.fetchall()

            if questions:
                game_state[chat_id] = {'questions': questions, 'current_question': 0, 'score': 0, 'quiz_id': quiz_id}
                await send_next_question(chat_id)
            else:
                await bot.send_message(chat_id, "В этой викторине нет вопросов.")

        elif action == "replay":
            quiz_id = int(quiz_id)
            async with lock:
                async with aiosqlite.connect('quiz.db') as db:
                    cursor = await db.cursor()
                    await cursor.execute("SELECT question, answer FROM questions WHERE quiz_id = ? ORDER BY RANDOM()", (quiz_id,))
                    questions = await cursor.fetchall()

            if questions:
                game_state[chat_id] = {'questions': questions, 'current_question': 0, 'score': 0, 'quiz_id': quiz_id}
                await send_next_question(chat_id)

        # сообщение о том, что выбор принят (необязательно)
        await bot.answer_callback_query(call.id, "Выбор принят!")

async def send_next_question(chat_id):
    if chat_id in game_state:
        current_question = game_state[chat_id]['current_question']
        questions = game_state[chat_id]['questions']
        if current_question < len(questions):
            question, answer = questions[current_question]
            game_state[chat_id]['current_question'] += 1
            game_state[chat_id]['answer'] = answer
            await bot.send_message(chat_id, question, reply_markup=get_main_keyboard())
        else:
            score = game_state[chat_id]['score']
            total_questions = len(questions)
            await bot.send_message(chat_id, f"Викторина завершена! Ваш счёт {score} из {total_questions}")
            await save_score(chat_id, game_state[chat_id]['quiz_id'], score)
            await ask_for_next_action(chat_id, game_state[chat_id]['quiz_id'])
            del game_state[chat_id]  # Очистка состояния игры

async def ask_for_next_action(chat_id, quiz_id):
    keyboard = types.InlineKeyboardMarkup()
    replay_button = types.InlineKeyboardButton(text="Пройти заново", callback_data=f"replay_{quiz_id}")
    new_quiz_button = types.InlineKeyboardButton(text="Другая викторина", callback_data="newquiz")
    keyboard.add(replay_button, new_quiz_button)
    await bot.send_message(chat_id, "Сыграем ещё?", reply_markup=keyboard)

def get_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    new_quiz_button = types.KeyboardButton("Новая викторина")
    change_mode_button = types.KeyboardButton("Смена режима")
    leaderboard_button = types.KeyboardButton("Лидерборд")
    keyboard.add(new_quiz_button, change_mode_button, leaderboard_button)
    return keyboard

@bot.message_handler(func=lambda message: message.text in ["Новая викторина", "Смена режима", "Лидерборд"])
async def handle_next_action(message):
    chat_id = message.chat.id
    if message.text == "Новая викторина":
        await start_quiz(message)
    elif message.text == "Смена режима":
        keyboard = types.InlineKeyboardMarkup()
        single_button = types.InlineKeyboardButton(text="Одиночная", callback_data="single")
        pvp_button = types.InlineKeyboardButton(text="PVP-викторина", callback_data="pvp")
        keyboard.add(single_button, pvp_button)
        await bot.send_message(chat_id, "Выбери тип викторины:", reply_markup=keyboard)
    elif message.text == "Лидерборд":
        await show_leaderboard(message)

# Обработчик ответов
@bot.message_handler(func=lambda message: True)
async def handle_answer(message):
    chat_id = message.chat.id
    if chat_id in game_state:
        correct_answer = game_state[chat_id]['answer']
        if message.text.lower() == correct_answer.lower():
            await bot.send_message(chat_id, "Правильно!")
            game_state[chat_id]['score'] += 1
        else:
            await bot.send_message(chat_id, "Неправильно!")

        # Отправляем следующий вопрос, если он есть
        await send_next_question(chat_id)

async def save_score(chat_id, quiz_id, score):
    chat = await bot.get_chat(chat_id)
    username = chat.username
    async with lock:
        async with aiosqlite.connect('quiz.db') as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT score FROM scores WHERE user_id = ? AND quiz_id = ?", (chat_id, quiz_id))
            existing_score = await cursor.fetchone()
            if existing_score is None or score > existing_score[0]:
                await cursor.execute("INSERT OR REPLACE INTO scores (user_id, username, quiz_id, score) VALUES (?, ?, ?, ?)",
                                   (chat_id, username, quiz_id, score))
                await db.commit()
                print(f"Score saved: {username} - {quiz_id} - {score}")

# Запуск бота
if __name__ == "__main__":
    # Инициализация базы данных
    result = asyncio.run(initialize_database())
    print(result)

    asyncio.run(bot.polling())
