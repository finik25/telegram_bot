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
        self.pvp_queue = []
        self.pvp_game_state = {}
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
            if chat_id in self.pvp_queue:
                await self.bot.send_message(chat_id, "Вы уже в очереди на PVP-викторину.")
            else:
                self.pvp_queue.append(chat_id)
                if len(self.pvp_queue) == 2:
                    player1, player2 = self.pvp_queue
                    await self.finish_quiz(player1, silent=True)
                    await self.finish_quiz(player2, silent=True)
                    await self.start_pvp_game(player1, player2)
                else:
                    keyboard = types.InlineKeyboardMarkup()
                    keyboard.add(types.InlineKeyboardButton(text="Покинуть очередь", callback_data="leave_queue"))
                    await self.bot.send_message(chat_id, "Вы добавлены в очередь на PVP-викторину. Пожалуйста, подождите второго игрока.", reply_markup=keyboard)
        elif call.data == "leave_queue":
            if chat_id in self.pvp_queue:
                self.pvp_queue.remove(chat_id)
                await self.bot.send_message(chat_id, "Вы покинули очередь на PVP-викторину.")
            else:
                await self.bot.send_message(chat_id, "Вы не в очереди на PVP-викторину.")
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

    async def start_pvp_game(self, player1, player2):
        player1_name = await self.get_username(player1)
        player2_name = await self.get_username(player2)
        await self.bot.send_message(player1, f"PVP-викторина начинается. Вы против игрока {player2_name}!")
        await self.bot.send_message(player2, f"PVP-викторина начинается. Вы против игрока {player1_name}!")
        await self.bot.send_message(player1, "Викторина начнётся через 10 секунд.")
        await self.bot.send_message(player2, "Викторина начнётся через 10 секунд.")
        await asyncio.sleep(10)

        questions = await self.fetch_questions_for_pvp()
        self.pvp_game_state[player1] = {'questions': questions, 'current_question': 0, 'score': 0, 'answered': False, 'correct_answer': False}
        self.pvp_game_state[player2] = {'questions': questions, 'current_question': 0, 'score': 0, 'answered': False, 'correct_answer': False}
        await self.send_next_pvp_question(player1, player2)

    async def fetch_questions_for_pvp(self):
        async with self.lock:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT question, answer FROM questions ORDER BY RANDOM() LIMIT 10")
                questions = await cursor.fetchall()
                if len(questions) < 10:
                    print("Warning: Less than 10 questions fetched for PVP game")
                return questions

    async def send_next_pvp_question(self, player1, player2):
        if player1 in self.pvp_game_state and player2 in self.pvp_game_state:
            current_question = self.pvp_game_state[player1]['current_question']
            questions = self.pvp_game_state[player1]['questions']

            # Проверка на выход за пределы списка
            if current_question < len(questions):
                question, answer = questions[current_question]
                self.pvp_game_state[player1]['current_question'] += 1
                self.pvp_game_state[player2]['current_question'] += 1
                self.pvp_game_state[player1]['answer'] = answer
                self.pvp_game_state[player2]['answer'] = answer
                self.pvp_game_state[player1]['answered'] = False
                self.pvp_game_state[player2]['answered'] = False
                self.pvp_game_state[player1]['correct_answer'] = False
                self.pvp_game_state[player2]['correct_answer'] = False
                await self.bot.send_message(player1, question)
                await self.bot.send_message(player2, question)
            else:
                await self.finish_pvp_game(player1, player2)
        else:
            print(f"Error: Player {player1} or {player2} not in pvp_game_state")
            self.pvp_queue = []  # Очистка очереди игроков в случае ошибки

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
                await cursor.execute("SELECT question, answer FROM questions WHERE quiz_id = ? ORDER BY RANDOM()", (quiz_id,))
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

    async def finish_quiz(self, chat_id, silent=False):
        if chat_id in self.game_state:
            score = self.game_state[chat_id]['score']
            total_questions = len(self.game_state[chat_id]['questions'])
            await self.save_score(chat_id, self.game_state[chat_id]['quiz_id'], score)
            if not silent:
                await self.ask_for_next_action(chat_id, self.game_state[chat_id]['quiz_id'])
            del self.game_state[chat_id]  # Очистка состояния игры
            if not silent:
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
        elif chat_id in self.pvp_game_state:
            opponent = self.get_opponent(chat_id)
            if opponent:
                correct_answer = self.pvp_game_state[chat_id]['answer']
                if message.text.lower() == correct_answer.lower():
                    if not self.pvp_game_state[opponent]['correct_answer']:
                        self.pvp_game_state[chat_id]['score'] += 1
                        self.pvp_game_state[chat_id]['correct_answer'] = True
                        player_name = await self.get_username(chat_id)
                        await self.bot.send_message(chat_id, "Верно!")
                        await self.bot.send_message(opponent, f"Игрок {player_name} ответил правильно!")
                        await self.send_next_pvp_question(chat_id, opponent)
                    else:
                        await self.bot.send_message(chat_id, "Ответ уже был дан другим игроком.")
                else:
                    self.pvp_game_state[chat_id]['answered'] = True
                    await self.bot.send_message(chat_id, "Не верно.")
                    if self.pvp_game_state[opponent]['answered']:
                        await self.send_next_pvp_question(chat_id, opponent)

    def get_opponent(self, player_id):
        for player, state in self.pvp_game_state.items():
            if player != player_id:
                return player
        return None

    async def finish_pvp_game(self, player1, player2):
        player1_name = await self.get_username(player1)
        player2_name = await self.get_username(player2)
        score1 = self.pvp_game_state[player1]['score']
        score2 = self.pvp_game_state[player2]['score']
        if score1 > score2:
            winner = player1_name
        elif score2 > score1:
            winner = player2_name
        else:
            winner = None

        if winner:
            await self.bot.send_message(player1,
                                        f"Викторина завершена! Победитель - {winner} ({score1} против {score2})")
            await self.bot.send_message(player2,
                                        f"Викторина завершена! Победитель - {winner} ({score2} против {score1})")
        else:
            await self.bot.send_message(player1, f"Викторина завершена! Ничья ({score1} против {score2})")
            await self.bot.send_message(player2, f"Викторина завершена! Ничья ({score2} против {score1})")

        # Сброс состояния игры
        del self.pvp_game_state[player1]
        del self.pvp_game_state[player2]
        self.pvp_queue = []  # Очистка очереди игроков

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

    async def get_username(self, chat_id):
        chat = await self.bot.get_chat(chat_id)
        return chat.username or "None"

    async def run(self):
        result = await self.database.initialize_database()
        print(result)
        await self.bot.polling()

# Запуск бота
if __name__ == "__main__":
    API_TOKEN = '8153449820:AAGrGlihbiwy4jTfOhhvzn1KI1Nrj4JQMGE'
    quiz_bot = QuizBot(API_TOKEN, 'quiz.db')
    asyncio.run(quiz_bot.run())
