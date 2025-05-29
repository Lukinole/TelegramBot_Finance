import logging
import json
import openai
import os
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, CallbackQueryHandler
from dotenv import load_dotenv
from command_broadcast import broadcast_start, broadcast_message, BROADCAST_MESSAGE
import sqlite3
import datetime
from command_report import report, handle_report_date_range
from command_category import category, button_handler
from constants import NORMAL_PROCESSING, ADD_TO_LIST, ADD_CATEGORY, DELETE_CATEGORY, EDIT_CATEGORY, EDIT_CATEGORY_NAME, EDIT_FOR_FILTER, NEW_TRANSACTION_DATA, XLSX, CSV, JSON, REPORT_DATE_RANGE, SET_DEFAULT_CURRENCY
from command_edit import edit, process_filter, button_handler2, process_new_transaction_data
from command_export import export_command, button_handler3
from command_currency import change_currency, currency_button_handler

class DatabaseManager:
    def __init__(self, db_file='user_info.db'):
        self.db_file = db_file

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_file)
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()

# Настройка логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

API_KEY = os.getenv("API_KEY")
TG_API = os.getenv("TG_API")

# Инициализация клиента OpenAI
openai.api_key = API_KEY

# Инициализация базы данных
def init_db():
    with DatabaseManager() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_data (
                user_id TEXT PRIMARY KEY,
                categories TEXT,
                default_currency TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                amount INTEGER,
                date DATE,
                category TEXT,
                currency TEXT,
                FOREIGN KEY(user_id) REFERENCES user_data(user_id)
            )
        ''')

def get_user_data(user_id):
    with DatabaseManager() as cursor:
        cursor.execute('SELECT categories, default_currency FROM user_data WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            categories = json.loads(row[0]) if row[0] else []
            default_currency = row[1]
            return {
                "categories": categories,
                "default_currency": default_currency
            }
        else:
            return {"categories": [], "default_currency": None}

def save_user_data(user_id, user_data):
    try:
        with DatabaseManager() as cursor:
            cursor.execute('''
                INSERT INTO user_data (user_id, categories, default_currency)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                categories=excluded.categories,
                default_currency=excluded.default_currency
            ''', (user_id, json.dumps(user_data["categories"]), user_data["default_currency"]))
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")

def save_transaction(user_id, amount, date, category, currency):
    with DatabaseManager() as cursor:
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, date, category, currency)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, amount, date, category, currency))

def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

async def start(update: Update, context: CallbackContext) -> None:
    """Отправляет сообщение при команде /start и убирает клавиатуру."""
    user_id = str(update.message.from_user.id)
    user_data = get_user_data(user_id)
    if not user_data["categories"]:
        save_user_data(user_id, user_data)

    # Сообщение приветствия и удаление клавиатуры
    await update.message.reply_text(
        "Привет! Я бот, который помогает вам вести учет своих расходов и доходов. Напишите мне любое сообщение с информацией о ваших расходах или доходах, и я добавлю её в ваш баланс.",
        reply_markup=ReplyKeyboardRemove()
    )   
    # Check if DefaultCurrency is empty or None
    if not user_data["default_currency"]:
        context.user_data['state'] = SET_DEFAULT_CURRENCY
        await update.message.reply_text("Пожалуйста, введите вашу валюту по умолчанию.")
        return

async def process_message(update: Update, context: CallbackContext) -> None:
    """Обработка сообщений в зависимости от текущего состояния."""
    user_id = str(update.message.from_user.id)
    user_message = update.message.text.strip()

    # Получаем текущее состояние
    current_state = context.user_data.get('state', NORMAL_PROCESSING)

    if current_state == SET_DEFAULT_CURRENCY:
        # Save the user's input as the default currency
        user_data = get_user_data(user_id)

        # Второй вызов ИИ для анализа и изменения баланса
        client = openai.OpenAI(api_key=API_KEY)
        Currency_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"""
                You are a helpful assistant that determines the currency of the transaction based on the user's message.
                Return the result strictly in JSON format with double quotes, like {{\"currency\": \"currency_symbol\"}}, where currency_symbol is the symbol of the currency like USD, EUR, UAH, etc."""},
                {"role": "user", "content": user_message}
            ]
        )
        Currency_bot_response = Currency_response.choices[0].message.content.strip()
        response_data = json.loads(Currency_bot_response)
        transaction_currency = response_data.get('currency', "USD")

        user_data["default_currency"] = transaction_currency
        save_user_data(user_id, user_data)
        context.user_data['state'] = NORMAL_PROCESSING
        await update.message.reply_text(f"Ваша валюта по умолчанию установлена на {transaction_currency}.")

        return




    if current_state == EDIT_FOR_FILTER:
        await process_filter(update, context)
    elif current_state == NEW_TRANSACTION_DATA:
        await process_new_transaction_data(update, context)
    elif current_state == NORMAL_PROCESSING:
        # Получение текущей даты
        current_date = datetime.datetime.now().date()

        # Получение категорий пользователя
        user_data = get_user_data(user_id)
        categories = user_data.get("categories", [])
        default_currency = user_data.get("default_currency")

        # Первый вызов ИИ для определения наличия доходов или расходов
        client = openai.OpenAI(api_key=API_KEY)
        query_type_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Determine if the user's message contains information about income or expenses. Return the result in JSON format like {\"contains_financial_info\": true} or {\"contains_financial_info\": false}."},
                {"role": "user", "content": user_message}
            ]
        )
        query_type_bot_response = query_type_response.choices[0].message.content.strip()

        try:
            contains_financial_info = json.loads(query_type_bot_response).get('contains_financial_info', False)
            if not contains_financial_info:
                await update.message.reply_text("Ваше сообщение не содержит информации о доходах или расходах.")
                return
        except json.JSONDecodeError as e:
            await update.message.reply_text(f"Произошла ошибка при обработке запроса. Пожалуйста, попробуйте снова. Ошибка: {e}")
            return

        # Второй вызов ИИ для анализа и изменения баланса
        balance_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"""
                Analyze the user's message to calculate the net change in balance based on income and expenses mentioned. 
                Also, determine the date of the transaction. If no date is mentioned, try to find it logically in the message. If no date is found, use the current date ({current_date}). 
                Additionally, categorize the transaction based on the user's categories: {categories}. if no category is found, use the category "Uncategorized" You must use only {categories} or "Uncategorized"!.
                Also, determine the currency of the transaction (use only symbols of currencies like USD, EUR, UAH, etc.). If no currency is mentioned, use the default currency ({default_currency}).
                Return the result strictly in JSON format with double quotes, like {{\"balance_change\": X, \"date\": \"YYYY-MM-DD\", \"category\": \"category_name\", \"currency\": \"currency_symbol\"}}, where X is the net change in balance as an integer, date is the transaction date, and category is the category of the transaction."""},
                {"role": "user", "content": user_message}
            ]
        )
        balance_bot_response = balance_response.choices[0].message.content.strip()

        # Parse the AI response
        try:
            response_data = json.loads(balance_bot_response)
            balance_change = response_data.get('balance_change', 0)
            transaction_date = response_data.get('date', current_date)
            transaction_category = response_data.get('category', 'Uncategorized')
            transaction_currency = response_data.get('currency', default_currency)

            # Save the transaction to the database
            save_transaction(user_id, balance_change, transaction_date, transaction_category, transaction_currency)

            save_user_data(user_id, user_data)

            
        except json.JSONDecodeError as e:
            await update.message.reply_text(f"Произошла ошибка при обработке изменения баланса. Пожалуйста, попробуйте снова. Ошибка: {e}")
            return

        # Третий вызов ИИ для генерации делового ответа
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"""
                You are a helpful assistant that summarizes the user's balance change and current total balance. use his content just to determine the language of the response and resopne in the same language (respone ony world "Uncategorized" in english if category is Uncategorized).
                Format the response: 
                "- last Change: {balance_change}. 
                
                - Date: {transaction_date}.

                - Category: {transaction_category}.
                
                - Currency: {transaction_currency}."
                The response should be short, clear, and formal."""},
                {"role": "user", "content": user_message}
            ]
        )
        bot_response = response.choices[0].message.content.strip()

        await update.message.reply_text(f"{bot_response}")
    elif current_state == ADD_TO_LIST:
        if 'list' not in context.user_data:
            context.user_data['list'] = []
        context.user_data['list'].append(user_message)
        await update.message.reply_text(f"Сообщение '{user_message}' добавлено в список.")
        context.user_data['state'] = NORMAL_PROCESSING
    elif current_state == ADD_CATEGORY:
        user_data = get_user_data(user_id)
        if 'categories' not in user_data:
            user_data['categories'] = []
        user_data['categories'].append(user_message)
        save_user_data(user_id, user_data)
        await update.message.reply_text(f"Категория '{user_message}' добавлена.")
        context.user_data['state'] = NORMAL_PROCESSING
    elif current_state == DELETE_CATEGORY:
        user_data = get_user_data(user_id)
        if user_message in user_data['categories']:
            user_data['categories'].remove(user_message)
            save_user_data(user_id, user_data)
            await update.message.reply_text(f"Категория '{user_message}' удалена.")
        else:
            await update.message.reply_text(f"Категория '{user_message}' не найдена.")
        context.user_data['state'] = NORMAL_PROCESSING
    elif current_state == EDIT_CATEGORY:
        user_data = get_user_data(user_id)
        if user_message in user_data['categories']:
            context.user_data['old_category'] = user_message
            await update.message.reply_text("Введите новое название категории:")
            context.user_data['state'] = EDIT_CATEGORY_NAME
        else:
            await update.message.reply_text(f"Категория '{user_message}' не найдена.")
            context.user_data['state'] = NORMAL_PROCESSING
    elif current_state == EDIT_CATEGORY_NAME:
        old_category = context.user_data.get('old_category')
        user_data = get_user_data(user_id)
        if old_category in user_data['categories']:
            index = user_data['categories'].index(old_category)
            user_data['categories'][index] = user_message
            save_user_data(user_id, user_data)

            # Update transactions in the database
            conn = sqlite3.connect('user_info.db')
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE transactions SET category = ? WHERE category = ? AND user_id = ?",
                (user_message, old_category, user_id)
            )
            conn.commit()
            conn.close()

            await update.message.reply_text(f"Категория '{old_category}' изменена на '{user_message}'.")
            context.user_data['state'] = NORMAL_PROCESSING  # Reset state only after successful update
        else:
            logger.warning(f"Old category '{old_category}' not found for user {user_id}")
    elif current_state == REPORT_DATE_RANGE:
        await handle_report_date_range(update, context)
    elif current_state == XLSX:
        await button_handler3(update, context)  
    elif current_state == CSV:
        await button_handler3(update, context)
    elif current_state == JSON:
        await button_handler3(update, context) 
    else:
        await update.message.reply_text(f"Ошибка при изменении категории.")


async def set_normal_processing(update: Update, context: CallbackContext) -> None:
    """Установить режим стандартной обработки сообщений."""
    context.user_data['state'] = NORMAL_PROCESSING
    await update.message.reply_text("Режим обработки сообщений установлен на стандартный.")

async def set_add_to_list(update: Update, context: CallbackContext) -> None:
    """Установить режим добавления сообщений в список."""
    context.user_data['state'] = ADD_TO_LIST
    await update.message.reply_text("Режим обработки сообщений установлен на добавление в список.")

def main() -> None:
    """Запуск бота."""
    init_db()
    application = ApplicationBuilder().token(TG_API).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("category", category))
    application.add_handler(CommandHandler("normal", set_normal_processing))
    application.add_handler(CommandHandler("addtolist", set_add_to_list))
    application.add_handler(CommandHandler("currency", change_currency))

    application.add_handler(CallbackQueryHandler(button_handler2, pattern=r'^transaction_\d+$|edit_transaction|delete_transaction|back_to_transactions$'))
    application.add_handler(CallbackQueryHandler(button_handler3, pattern=r'^(xlsx|csv|json|go_back)$'))
    application.add_handler(CallbackQueryHandler(button_handler, pattern=r'^(add_category|delete_category|edit_category)$'))
    application.add_handler(CallbackQueryHandler(currency_button_handler, pattern=r'^(change_currency|go_back)$'))

    # Обработчик для команды /broadcast
    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)],
        },
        fallbacks=[],
    )
    application.add_handler(broadcast_handler)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))

    # Register the /edit command handler
    application.add_handler(CommandHandler("edit", edit))

    # Register the /export command handler
    application.add_handler(CommandHandler("export", export_command))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
