import asyncio
from telebot.async_telebot import AsyncTeleBot
from command_handler import CommandHandler
from message_handler import MessageHandler
from game_state_manager import GameStateManager
from pvp_quiz_manager import PVPQuizManager
from database import Database

class QuizBot:
    def __init__(self, api_token, db_name):
        self.bot = AsyncTeleBot(api_token)
        self.database = Database(db_name)

        # Инициализация всех компонентов
        self.command_handler = CommandHandler(self.bot, self.database)
        self.game_state_manager = GameStateManager(self.bot)
        self.pvp_quiz_manager = PVPQuizManager(self.bot)

        # Передача необходимых атрибутов в MessageHandler
        self.message_handler = MessageHandler(
            self.bot,
            self.pvp_quiz_manager.pvp_queue,
            self.pvp_quiz_manager.pvp_game_state,
            self.game_state_manager.game_state,
            self.game_state_manager,
            self.pvp_quiz_manager,
            self.database
        )

        self.setup_handlers()

    def setup_handlers(self):
        self.command_handler.setup_handlers()
        self.message_handler.setup_handlers()

    async def run(self):
        result = await self.database.initialize_database()
        print(result)
        await self.bot.polling()

# Запуск бота
if __name__ == "__main__":
    API_TOKEN = '8153449820:AAGrGlihbiwy4jTfOhhvzn1KI1Nrj4JQMGE'
    quiz_bot = QuizBot(API_TOKEN, 'quiz.db')
    asyncio.run(quiz_bot.run())
