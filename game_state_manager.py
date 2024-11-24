import aiosqlite
from telebot import types

class GameStateManager:
    def __init__(self, bot):
        self.bot = bot
        self.game_state = {}

    async def start_quiz_game(self, chat_id, quiz_id):
        questions = await self.fetch_questions(quiz_id)

        if questions:
            self.game_state[chat_id] = {'questions': questions, 'current_question': 0, 'score': 0, 'quiz_id': quiz_id}
            await self.send_next_question(chat_id)
        else:
            await self.bot.send_message(chat_id, "В этой викторине нет вопросов.")

    async def fetch_questions(self, quiz_id):
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
                await self.bot.send_message(chat_id, f"Викторина завершена! Ваш счёт {score} из {total_questions}", reply_markup=self.get_main_keyboard())
                await self.ask_for_next_action(chat_id, self.game_state[chat_id]['quiz_id'])
            del self.game_state[chat_id]  # Очистка состояния игры

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

    async def save_score(self, chat_id, quiz_id, score):
        chat = await self.bot.get_chat(chat_id)
        username = chat.username
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
