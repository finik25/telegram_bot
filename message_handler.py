import aiosqlite
from telebot import types

class MessageHandler:
    def __init__(self, bot, pvp_queue, pvp_game_state, game_state, game_state_manager, pvp_quiz_manager):
        self.bot = bot
        self.pvp_queue = pvp_queue
        self.pvp_game_state = pvp_game_state
        self.game_state = game_state
        self.game_state_manager = game_state_manager
        self.pvp_quiz_manager = pvp_quiz_manager

    def setup_handlers(self):
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_quiz_selection)
        self.bot.message_handler(func=lambda message: message.text in ["Новая викторина", "Смена режима", "Лидерборд"])(
            self.handle_next_action)
        self.bot.message_handler(func=lambda message: True)(self.handle_answer)

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
                    await self.game_state_manager.finish_quiz(player1, silent=True)
                    await self.game_state_manager.finish_quiz(player2, silent=True)
                    await self.pvp_quiz_manager.start_pvp_game(player1, player2)
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
                await self.game_state_manager.start_quiz_game(chat_id, int(quiz_id))
            elif action == "replay":
                await self.replay_quiz(chat_id, int(quiz_id))

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
            await self.game_state_manager.send_next_question(chat_id)
        elif chat_id in self.pvp_game_state:
            opponent = self.get_opponent(chat_id)
            if opponent:
                correct_answer = self.pvp_game_state[chat_id]['answer']
                if message.text.lower() == correct_answer.lower():
                    if not self.pvp_game_state[opponent]['correct_answer']:
                        self.pvp_game_state[chat_id]['score'] += 1
                        self.pvp_game_state[chat_id]['correct_answer'] = True
                        player_name = await self.pvp_quiz_manager.get_username(chat_id)
                        await self.bot.send_message(chat_id, "Верно!")
                        await self.bot.send_message(opponent, f"Игрок {player_name} ответил правильно!")
                        await self.pvp_quiz_manager.send_next_pvp_question(chat_id, opponent)
                    else:
                        await self.bot.send_message(chat_id, "Ответ уже был дан другим игроком.")
                else:
                    self.pvp_game_state[chat_id]['answered'] = True
                    await self.bot.send_message(chat_id, "Не верно.")
                    if self.pvp_game_state[opponent]['answered']:
                        await self.pvp_quiz_manager.send_next_pvp_question(chat_id, opponent)

    def get_opponent(self, player_id):
        for player, state in self.pvp_game_state.items():
            if player != player_id:
                return player
        return None

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
        async with aiosqlite.connect('quiz.db') as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT name FROM quizzes WHERE id = ?", (quiz_id,))
            return (await cursor.fetchone())[0]

    async def replay_quiz(self, chat_id, quiz_id):
        await self.game_state_manager.start_quiz_game(chat_id, quiz_id)

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
                await self.game_state_manager.finish_quiz(chat_id)

    async def send_next_pvp_question(self, player1, player2):
        if player1 in self.pvp_game_state and player2 in self.pvp_game_state:
            current_question = self.pvp_game_state[player1]['current_question']
            questions = self.pvp_game_state[player1]['questions']
            if current_question < len(questions):
                question, answer = questions[current_question]
                self.pvp_game_state[player1]['current_question'] += 1
                self.pvp_game_state[player1]['answer'] = answer
                self.pvp_game_state[player2]['current_question'] += 1
                self.pvp_game_state[player2]['answer'] = answer
                await self.bot.send_message(player1, question)
                await self.bot.send_message(player2, question)
            else:
                await self.pvp_quiz_manager.finish_pvp_game(player1, player2)
