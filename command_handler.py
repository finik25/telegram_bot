import aiosqlite
from telebot import types
from database import Database

class CommandHandler:
    def __init__(self, bot):
        self.bot = bot
        self.database = Database('quiz.db')

    def setup_handlers(self):
        self.bot.message_handler(commands=['start'])(self.send_welcome)
        self.bot.message_handler(commands=['quiz'])(self.start_quiz_command)
        self.bot.message_handler(commands=['leaderboard'])(self.show_leaderboard_command)
        self.bot.message_handler(commands=['clear_leaderboard'])(self.clear_leaderboard_command)

    async def send_welcome(self, message):
        chat_id = message.chat.id
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(text="Одиночная", callback_data="single"),
            types.InlineKeyboardButton(text="PVP-викторина", callback_data="pvp")
        )
        await self.bot.send_message(chat_id, "Привет! Выбери тип викторины:", reply_markup=keyboard)

    async def start_quiz_command(self, message):
        # вызов соответствующего метода в MessageHandler
        await self.start_quiz(message)

    async def show_leaderboard_command(self, message):
        # вызов соответствующего метода в MessageHandler
        await self.show_leaderboard(message)

    async def clear_leaderboard_command(self, message):
        chat_id = message.chat.id
        await self.database.clear_leaderboard()
        await self.bot.send_message(chat_id, "Лидерборд успешно очищен.")
