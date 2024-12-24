import aiosqlite
from telebot import types
from database import Database
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, bot, database):
        """
        Инициализация обработчика команд.
        :param bot: Экземпляр бота.
        :param database: Экземпляр базы данных.
        """
        self.bot = bot
        self.database = database

    def setup_handlers(self):
        """
        Установка обработчиков команд.
        """
        self.bot.message_handler(commands=['start'])(self.send_welcome)
        self.bot.message_handler(commands=['quiz'])(self.start_quiz_command)
        self.bot.message_handler(commands=['leaderboard'])(self.show_leaderboard_command)
        self.bot.message_handler(commands=['clear_leaderboard'])(self.clear_leaderboard_command)
        self.bot.message_handler(commands=['manage_quizzes'])(self.manage_quizzes_command)  # управление викторинами

    async def send_welcome(self, message):
        """
        Обработчик команды /start.
        :param message: Объект сообщения.
        """
        try:
            chat_id = message.chat.id
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(text="Одиночная", callback_data="single"),
                types.InlineKeyboardButton(text="PVP-викторина", callback_data="pvp")
            )
            await self.bot.send_message(chat_id, "Привет! Выбери тип викторины:", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")

    async def start_quiz_command(self, message):
        """
        Обработчик команды /quiz.
        :param message: Объект сообщения.
        """
        try:
            await self.start_quiz(message)
        except Exception as e:
            logger.error(f"Error starting quiz: {e}")

    async def show_leaderboard_command(self, message):
        """
        Обработчик команды /leaderboard.
        :param message: Объект сообщения.
        """
        try:
            await self.show_leaderboard(message)
        except Exception as e:
            logger.error(f"Error showing leaderboard: {e}")

    async def clear_leaderboard_command(self, message):
        """
        Обработчик команды /clear_leaderboard.
        :param message: Объект сообщения.
        """
        try:
            chat_id = message.chat.id
            await self.database.clear_leaderboard()
            await self.bot.send_message(chat_id, "Лидерборд успешно очищен.")
        except Exception as e:
            logger.error(f"Error clearing leaderboard: {e}")

    async def manage_quizzes_command(self, message):
        """
        Обработчик команды /manage_quizzes.
        :param message: Объект сообщения.
        """
        try:
            chat_id = message.chat.id
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(text="Добавить викторину", callback_data="add_quiz"),
                types.InlineKeyboardButton(text="Обновить викторину", callback_data="update_quiz"),
                types.InlineKeyboardButton(text="Удалить викторину", callback_data="delete_quiz")
            )
            await self.bot.send_message(chat_id, "Выберите действие:", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error managing quizzes: {e}")
