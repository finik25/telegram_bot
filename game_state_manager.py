import aiosqlite
from telebot import types
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameStateManager:
    def __init__(self, bot):
        self.bot = bot
        self.game_state = {}

    async def start_quiz_game(self, chat_id, quiz_id):
        try:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT question, answer FROM questions WHERE quiz_id = ? ORDER BY RANDOM()", (quiz_id,))
                questions = await cursor.fetchall()
                if questions:
                    self.game_state[chat_id] = {
                        'questions': questions,
                        'current_question': 0,
                        'score': 0,
                        'answer': None,
                        'quiz_id': quiz_id
                    }
                    await self.send_next_question(chat_id)
                else:
                    await self.bot.send_message(chat_id, "Викторина не найдена.")
        except Exception as e:
            logger.error(f"Error starting quiz game: {e}")

    async def fetch_questions(self, quiz_id):
        try:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT question, answer FROM questions WHERE quiz_id = ? ORDER BY RANDOM()", (quiz_id,))
                return await cursor.fetchall()
        except Exception as e:
            logger.error(f"Error fetching questions: {e}")
            return []

    async def replay_quiz(self, chat_id, quiz_id):
        try:
            await self.start_quiz_game(chat_id, quiz_id)
        except Exception as e:
            logger.error(f"Error replaying quiz: {e}")

    async def send_next_question(self, chat_id):
        try:
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
        except Exception as e:
            logger.error(f"Error sending next question: {e}")

    async def finish_quiz(self, chat_id, silent=False):
        try:
            if chat_id in self.game_state:
                score = self.game_state[chat_id]['score']
                total_questions = len(self.game_state[chat_id]['questions'])
                await self.save_score(chat_id, self.game_state[chat_id]['quiz_id'], score)
                if not silent:
                    await self.bot.send_message(chat_id, f"Викторина завершена! Ваш счёт {score} из {total_questions}", reply_markup=self.get_main_keyboard())
                    await self.ask_for_next_action(chat_id, self.game_state[chat_id]['quiz_id'])
                del self.game_state[chat_id]  # Очистка состояния игры
        except Exception as e:
            logger.error(f"Error finishing quiz: {e}")

    async def ask_for_next_action(self, chat_id, quiz_id):
        try:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(text="Пройти заново", callback_data=f"replay_{quiz_id}"),
                types.InlineKeyboardButton(text="Другая викторина", callback_data="newquiz")
            )
            await self.bot.send_message(chat_id, "Сыграем ещё?", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error asking for next action: {e}")

    def get_main_keyboard(self):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(
            types.KeyboardButton("Новая викторина"),
            types.KeyboardButton("Смена режима"),
            types.KeyboardButton("Лидерборд")
        )
        return keyboard

    async def save_score(self, chat_id, quiz_id, score):
        try:
            chat = await self.bot.get_chat(chat_id)
            username = chat.username
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT score FROM scores WHERE user_id = ? AND quiz_id = ?", (chat_id, quiz_id))
                existing_score = await cursor.fetchone()

                # Получаем название викторины по её ID
                await cursor.execute("SELECT name FROM quizzes WHERE id = ?", (quiz_id,))
                quiz_name = await cursor.fetchone()
                quiz_name = quiz_name[0] if quiz_name else "Unknown Quiz"

                # Сравниваем лучший результат
                if existing_score is None or score > existing_score[0]:
                    await cursor.execute(
                        "INSERT OR REPLACE INTO scores (user_id, username, quiz_id, score) VALUES (?, ?, ?, ?)",
                        (chat_id, username, quiz_id, score))
                    await db.commit()
                    logger.info(f"Score saved: {username} - {quiz_name} - {score}")
        except Exception as e:
            logger.error(f"Error saving score: {e}")
