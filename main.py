import asyncio
import aiosqlite
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from database import Database

class QuizBot:
    def __init__(self, api_token, db_name):
        self.bot = AsyncTeleBot(api_token)
        self.database = Database(db_name)
        self.lock = asyncio.Lock()
        self.game_state = {}
        self.bot_handlers()

    def bot_handlers(self):
        self.bot.message_handler(commands=['start'])(self.send_welcome)
        self.bot.message_handler(commands=['quiz'])(self.start_quiz)
        self.bot.message_handler(commands=['leaderboard'])(self.show_leaderboard)
        self.bot.message_handler(commands=['clear_leaderboard'])(self.clear_leaderboard_command)
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_quiz_selection)
        self.bot.message_handler(func=lambda message: message.text in ["Новая викторина", "Смена режима", "Лидерборд"])(
            self.handle_next_action)
        self.bot.message_handler(func=lambda message: True)(self.handle_answer)

    async def send_welcome(self, message):
        chat_id = message.chat.id
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(text="Одиночная", callback_data="single"),
            types.InlineKeyboardButton(text="PVP-викторина", callback_data="pvp")
        )
        await self.bot.send_message(chat_id, "Привет! Выбери тип викторины:", reply_markup=keyboard)

    async def start_quiz(self, message):
        chat_id = message.chat.id
        quizzes = await self.get_quizzes()

        if quizzes:
            keyboard = types.InlineKeyboardMarkup()
            for quiz_id, quiz_name in quizzes:
                keyboard.add(types.InlineKeyboardButton(text=quiz_name, callback_data=f"quiz_{quiz_id}"))
            await self.bot.send_message(chat_id, "Выбери викторину:", reply_markup=keyboard)
        else:
            await self.bot.send_message(chat_id, "Нет доступных викторин.")

    async def get_quizzes(self):
        async with self.lock:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT id, name FROM quizzes")
                return await cursor.fetchall()

    async def show_leaderboard(self, message):
        chat_id = message.chat.id
        leaderboard = await self.fetch_leaderboard()

        if leaderboard:
            best_scores = {}
            for username, quiz_id, score, total_questions in leaderboard:
                if username not in best_scores or (
                        score / total_questions > best_scores[username]['score'] / best_scores[username]['total_questions']):
                    quiz_name = await self.fetch_quiz_name(quiz_id)
                    best_scores[username] = {
                        'quiz_name': quiz_name,
                        'score': int(score),  # Convert score to integer
                        'total_questions': total_questions
                    }

            response = "Лидерборд:\n"
            for position, (username, data) in enumerate(
                    sorted(best_scores.items(), key=lambda x: x[1]['score'] / x[1]['total_questions'], reverse=True),
                    start=1):
                response += (f"{position}. {username} - {data['quiz_name']}: "
                             f"{data['score']}/{data['total_questions']} "
                             f"({data['score'] / data['total_questions'] * 100:.2f}%)\n")
            await self.bot.send_message(chat_id, response)
        else:
            await self.bot.send_message(chat_id, "Лидерборд пока пуст.")

    async def fetch_leaderboard(self):
        async with self.lock:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("""
                    SELECT username, quiz_id, score,
                           (SELECT COUNT(*) FROM questions WHERE quiz_id = scores.quiz_id) as total_questions
                    FROM scores
                    ORDER BY score DESC
                """)
                return await cursor.fetchall()

    async def fetch_quiz_name(self, quiz_id):
        async with self.lock:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT name FROM quizzes WHERE id = ?", (quiz_id,))
                return (await cursor.fetchone())[0]

    async def clear_leaderboard_command(self, message):
        chat_id = message.chat.id
        await self.database.clear_leaderboard()
        await self.bot.send_message(chat_id, "Лидерборд успешно очищен.")

    async def handle_quiz_selection(self, call):
        chat_id = call.message.chat.id
        if call.data == "single":
            await self.start_quiz(call.message)
        elif call.data == "pvp":
            await self.bot.send_message(chat_id, "Функция PVP-викторины пока недоступна.")
        elif call.data == "newquiz":
            await self.start_quiz(call.message)
        else:
            try:
                action, quiz_id = call.data.split('_')
            except ValueError:
                return

            if action == "quiz":
                await self.start_quiz_game(chat_id, int(quiz_id))
            elif action == "replay":
                await self.replay_quiz(chat_id, int(quiz_id))

    async def start_quiz_game(self, chat_id, quiz_id):
        questions = await self.fetch_questions(quiz_id)

        if questions:
            self.game_state[chat_id] = {'questions': questions, 'current_question': 0, 'score': 0, 'quiz_id': quiz_id}
            await self.send_next_question(chat_id)
        else:
            await self.bot.send_message(chat_id, "В этой викторине нет вопросов.")

    async def fetch_questions(self, quiz_id):
        async with self.lock:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT question, answer FROM questions WHERE quiz_id = ? ORDER BY RANDOM()",
                                     (quiz_id,))
                return await cursor.fetchall()

    async def replay_quiz(self, chat_id, quiz_id):
        await self.start_quiz_game(chat_id, quiz_id)

    async def send_next_question(self, chat_id):
        if chat_id in self.game_state:
            current_question = self.game_state[chat_id]['current_question']
            questions = self.game_state[chat_id]['questions']
            if current_question < len(questions):
                question, answer = questions[current_question]
                self.game_state[chat_id]['current_question'] += 1
                self.game_state[chat_id]['answer'] = answer
                await self.bot.send_message(chat_id, question)
            else:
                await self.finish_quiz(chat_id)

    async def finish_quiz(self, chat_id):
        score = self.game_state[chat_id]['score']
        total_questions = len(self.game_state[chat_id]['questions'])
        await self.save_score(chat_id, self.game_state[chat_id]['quiz_id'], score)
        await self.ask_for_next_action(chat_id, self.game_state[chat_id]['quiz_id'])
        del self.game_state[chat_id]  # Очистка состояния игры
        await self.bot.send_message(chat_id, f"Викторина завершена! Ваш счёт {score} из {total_questions}", reply_markup=self.get_main_keyboard())

    async def ask_for_next_action(self, chat_id, quiz_id):
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(text="Пройти заново", callback_data=f"replay_{quiz_id}"),
            types.InlineKeyboardButton(text="Другая викторина", callback_data="newquiz")
        )
        await self.bot.send_message(chat_id, "Сыграем ещё?", reply_markup=keyboard)

    def get_main_keyboard(self):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(
            types.KeyboardButton("Новая викторина"),
            types.KeyboardButton("Смена режима"),
            types.KeyboardButton("Лидерборд")
        )
        return keyboard

    async def handle_next_action(self, message):
        chat_id = message.chat.id
        if message.text == "Новая викторина":
            await self.start_quiz(message)
        elif message.text == "Смена режима":
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(text="Одиночная", callback_data="single"),
                types.InlineKeyboardButton(text="PVP-викторина", callback_data="pvp")
            )
            await self.bot.send_message(chat_id, "Выбери тип викторины:", reply_markup=keyboard)
        elif message.text == "Лидерборд":
            await self.show_leaderboard(message)

    async def handle_answer(self, message):
        chat_id = message.chat.id
        if chat_id in self.game_state:
            correct_answer = self.game_state[chat_id]['answer']
            if message.text.lower() == correct_answer.lower():
                await self.bot.send_message(chat_id, "Правильно!")
                self.game_state[chat_id]['score'] += 1
            else:
                await self.bot.send_message(chat_id, "Неправильно!")

            # Отправляем следующий вопрос, если он есть
            await self.send_next_question(chat_id)

    async def save_score(self, chat_id, quiz_id, score):
        chat = await self.bot.get_chat(chat_id)
        username = chat.username
        async with self.lock:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT score FROM scores WHERE user_id = ? AND quiz_id = ?", (chat_id, quiz_id))
                existing_score = await cursor.fetchone()

                # Сравниваем лучший результат
                if existing_score is None or score > existing_score[0]:
                    await cursor.execute(
                        "INSERT OR REPLACE INTO scores (user_id, username, quiz_id, score) VALUES (?, ?, ?, ?)",
                        (chat_id, username, quiz_id, score))
                    await db.commit()
                    print(f"Score saved: {username} - {quiz_id} - {score}")

    async def run(self):
        result = await self.database.initialize_database()
        print(result)
        await self.bot.polling()

if __name__ == "__main__":
    API_TOKEN = '8153449820:AAGrGlihbiwy4jTfOhhvzn1KI1Nrj4JQMGE'
    quiz_bot = QuizBot(API_TOKEN, 'quiz.db')
    asyncio.run(quiz_bot.run())
