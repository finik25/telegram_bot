import os
import asyncio
import logging
from telebot.async_telebot import AsyncTeleBot
from command_handler import CommandHandler
from message_handler import MessageHandler
from game_state_manager import GameStateManager
from pvp_quiz_manager import PVPQuizManager
from database import Database

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuizBot:
    def __init__(self, db_name):
        """
        Инициализация бота.
        :param db_name: Имя базы данных.
        """
        self.api_token = os.getenv('API_TOKEN')
        if not self.api_token:
            raise ValueError("API_TOKEN environment variable is not set")
        self.bot = AsyncTeleBot(self.api_token)
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
        """
        Установка обработчиков команд и сообщений.
        """
        self.command_handler.setup_handlers()
        self.message_handler.setup_handlers()

    async def run(self):
        """
        Запуск бота.
        """
        try:
            result = await self.database.initialize_database()
            logger.info(result)
            await self.bot.polling()
        except Exception as e:
            logger.error(f"Error during bot initialization: {e}")

# Запуск бота
if __name__ == "__main__":
    try:
        quiz_bot = QuizBot('quiz.db')
        asyncio.run(quiz_bot.run())
    except Exception as e:
        logger.error(f"Error during bot start: {e}")
