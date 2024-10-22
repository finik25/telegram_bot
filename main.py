import telebot
from telebot import types
import sqlite3
from threading import Lock
from database import initialize_database

API_TOKEN = '8153449820:AAGrGlihbiwy4jTfOhhvzn1KI1Nrj4JQMGE'
bot = telebot.TeleBot(API_TOKEN)

# Блокировка для синхронизации доступа к базе данных
lock = Lock()

# Создание таблиц для викторин и вопросов
conn = sqlite3.connect('quiz.db', check_same_thread=False)
cursor = conn.cursor()

# Хранилище состояния игры
game_state = {}

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Начнем викторину? Напиши /quiz")

# Обработчик команды /quiz
@bot.message_handler(commands=['quiz'])
def start_quiz(message):
    chat_id = message.chat.id
    with lock:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM quizzes")
        quizzes = cursor.fetchall()

    if quizzes:
        keyboard = types.InlineKeyboardMarkup()
        for quiz_id, quiz_name in quizzes:
            button = types.InlineKeyboardButton(text=quiz_name, callback_data=f"quiz_{quiz_id}")
            keyboard.add(button)
        bot.send_message(chat_id, "Выбери викторину:", reply_markup=keyboard)
    else:
        bot.send_message(chat_id, "Нет доступных викторин.")

# Обработчик callback-запросов
@bot.callback_query_handler(func=lambda call: True)
def handle_quiz_selection(call):
    chat_id = call.message.chat.id
    quiz_id = int(call.data.split('_')[1])
    print(f"Callback data received: {call.data}")  # Логирование для отладки
    with lock:
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer FROM questions WHERE quiz_id = ? ORDER BY RANDOM()", (quiz_id,))
        questions = cursor.fetchall()

    if questions:
        game_state[chat_id] = {'questions': questions, 'current_question': 0}
        send_next_question(chat_id)
    else:
        bot.send_message(chat_id, "В этой викторине нет вопросов.")

    # сообщение о том, что выбор принят (необязательно)
    bot.answer_callback_query(call.id, "Выбор принят!")  # Это важно, чтобы пользователь видел отклик

def send_next_question(chat_id):
    if chat_id in game_state:
        current_question = game_state[chat_id]['current_question']
        questions = game_state[chat_id]['questions']
        if current_question < len(questions):
            question, answer = questions[current_question]
            game_state[chat_id]['current_question'] += 1
            game_state[chat_id]['answer'] = answer
            bot.send_message(chat_id, question)
        else:
            bot.send_message(chat_id, "Викторина завершена!")
            del game_state[chat_id]  # Очистка состояния игры
            ask_for_next_action(chat_id)

def ask_for_next_action(chat_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    new_quiz_button = types.KeyboardButton("Новая викторина")
    change_mode_button = types.KeyboardButton("Смена режима")
    exit_button = types.KeyboardButton("Выход")
    keyboard.add(new_quiz_button, change_mode_button, exit_button)
    bot.send_message(chat_id, "Что вы хотите сделать?", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text in ["Новая викторина", "Смена режима", "Выход"])
def handle_next_action(message):
    chat_id = message.chat.id
    if message.text == "Новая викторина":
        start_quiz(message)
    elif message.text == "Смена режима":
        bot.send_message(chat_id, "Функция 'Смена режима' пока недоступна.")
    elif message.text == "Выход":
        bot.send_message(chat_id, "Было здорово, приходите еще!")


# Обработчик ответов
@bot.message_handler(func=lambda message: True)
def handle_answer(message):
    chat_id = message.chat.id
    if chat_id in game_state:
        correct_answer = game_state[chat_id]['answer']
        if message.text.lower() == correct_answer.lower():
            bot.send_message(chat_id, "Правильно!")
        else:
            bot.send_message(chat_id, "Неправильно!")

        # Отправляем следующий вопрос, если он есть
        send_next_question(chat_id)

# Запуск бота
if __name__ == "__main__":
    # Инициализация базы данных
    print(initialize_database())

    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Ошибка: {e}")
