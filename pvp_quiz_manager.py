import asyncio
import aiosqlite
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PVPQuizManager:
    def __init__(self, bot):
        self.bot = bot
        self.pvp_game_state = {}
        self.pvp_queue = []

    async def start_pvp_game(self, player1, player2):
        try:
            player1_name = await self.get_username(player1)
            player2_name = await self.get_username(player2)

            await self.bot.send_message(player1, f"PVP-викторина начинается. Вы против игрока {player2_name}!")
            await self.bot.send_message(player2, f"PVP-викторина начинается. Вы против игрока {player1_name}!")

            await self.bot.send_message(player1, "Викторина начнётся через 10 секунд. Победит тот, кто первым ответит правильно на большее число вопросов.")
            await self.bot.send_message(player2, "Викторина начнётся через 10 секунд. Победит тот, кто первым ответит правильно на большее число вопросов.")

            await asyncio.sleep(10)

            questions = await self.fetch_questions_for_pvp()
            self.pvp_game_state[player1] = {'questions': questions, 'current_question': 0, 'score': 0, 'answered': False, 'correct_answer': False}
            self.pvp_game_state[player2] = {'questions': questions, 'current_question': 0, 'score': 0, 'answered': False, 'correct_answer': False}
            await self.send_next_pvp_question(player1, player2)
        except Exception as e:
            logger.error(f"Error starting PVP game: {e}")

    async def send_next_pvp_question(self, player1, player2):
        try:
            if player1 in self.pvp_game_state and player2 in self.pvp_game_state:
                current_question = self.pvp_game_state[player1]['current_question']
                questions = self.pvp_game_state[player1]['questions']

                if current_question < len(questions):
                    # Обратный отсчет перед выводом вопроса
                    countdown_message1 = await self.bot.send_message(player1, "Следующий вопрос через 3 секунды...")
                    countdown_message2 = await self.bot.send_message(player2, "Следующий вопрос через 3 секунды...")

                    for i in range(2, -1, -1):
                        await asyncio.sleep(1)
                        await self.bot.edit_message_text(chat_id=countdown_message1.chat.id, message_id=countdown_message1.message_id, text=f"Следующий вопрос через {i} секунд...")
                        await self.bot.edit_message_text(chat_id=countdown_message2.chat.id, message_id=countdown_message2.message_id, text=f"Следующий вопрос через {i} секунд...")

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
                logger.error(f"Error: Player {player1} or {player2} not in pvp_game_state")
                self.pvp_queue = []  # Очистка очереди игроков в случае ошибки
        except Exception as e:
            logger.error(f"Error sending next PVP question: {e}")

    async def fetch_questions_for_pvp(self):
        try:
            async with aiosqlite.connect('quiz.db') as db:
                cursor = await db.cursor()
                await cursor.execute("SELECT question, answer FROM questions ORDER BY RANDOM() LIMIT 10")
                questions = await cursor.fetchall()
                if len(questions) < 10:
                    logger.warning("Warning: Less than 10 questions fetched for PVP game")
                return questions
        except Exception as e:
            logger.error(f"Error fetching questions for PVP: {e}")
            return []

    async def finish_pvp_game(self, player1, player2):
        try:
            player1_name = await self.get_username(player1)
            player2_name = await self.get_username(player2)
            score1 = self.pvp_game_state[player1]['score']
            score2 = self.pvp_game_state[player2]['score']

            if score1 > score2:
                await self.bot.send_message(player1, f"Викторина завершена! Вы победили! ({score1} против {score2})")
                await self.bot.send_message(player2, f"Викторина завершена! Победитель - {player1_name} ({score1} против {score2})")
            elif score2 > score1:
                await self.bot.send_message(player2, f"Викторина завершена! Вы победили! ({score2} против {score1})")
                await self.bot.send_message(player1, f"Викторина завершена! Победитель - {player2_name} ({score2} против {score1})")
            else:
                await self.bot.send_message(player1, f"Викторина завершена! Ничья ({score1} против {score2})")
                await self.bot.send_message(player2, f"Викторина завершена! Ничья ({score2} против {score1})")

            # Сброс состояния игры
            del self.pvp_game_state[player1]
            del self.pvp_game_state[player2]
            self.pvp_queue = []  # Очистка очереди игроков
        except Exception as e:
            logger.error(f"Error finishing PVP game: {e}")

    async def get_username(self, chat_id):
        try:
            chat = await self.bot.get_chat(chat_id)
            return chat.username or "None"
        except Exception as e:
            logger.error(f"Error getting username: {e}")
            return "None"
