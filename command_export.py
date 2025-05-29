import sqlite3
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
import os
from openpyxl import load_workbook
from constants import NORMAL_PROCESSING, XLSX, CSV, JSON
import json
from fpdf import FPDF
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

@contextmanager
def safe_file_operation(file_path, mode='rb'):
    """Контекстный менеджер для безопасной работы с файлами."""
    try:
        with open(file_path, mode) as file:
            yield file
    except Exception as e:
        logger.error(f"Error working with file {file_path}: {e}")
        raise
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {e}")

async def export_command(update: Update, context: CallbackContext) -> None:
    """Handles the /export command by sending a greeting message and an Excel file of transactions."""
    message = f"Выберите Формат:"

    keyboard = [
        [InlineKeyboardButton(".xlsx", callback_data='xlsx')],
        [InlineKeyboardButton(".csv", callback_data='csv')],
        [InlineKeyboardButton(".json", callback_data='json')],
        [InlineKeyboardButton("<- назад", callback_data='go_back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)

async def button_handler3(update: Update, context: CallbackContext) -> None:
    """Обрабатывает нажатие кнопки."""
    query = update.callback_query
    await query.answer()

    try:
        user_id = str(query.from_user.id)
        
        # Connect to the database and fetch transactions for the user
        with sqlite3.connect('user_info.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT date, amount, category, currency FROM transactions WHERE user_id = ?', (user_id,))
            transactions = cursor.fetchall()

        # Create a DataFrame from the transactions
        df = pd.DataFrame(transactions, columns=['Date', 'Amount', 'Category', 'Currency'])

        # Convert 'Date' to datetime for sorting, then back to string
        df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
        df.sort_values(by='Date', inplace=True)
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

        if query.data == 'xlsx':
            context.user_data['state'] = XLSX
            file_path = f"{user_id}_transactions.xlsx"
            
            # Save the DataFrame to an Excel file
            df.to_excel(file_path, index=False)

            # Adjust column width
            workbook = load_workbook(file_path)
            worksheet = workbook.active
            for column in worksheet.columns:
                max_length = 0
                column = list(column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
            workbook.save(file_path)

            # Send the Excel file
            with safe_file_operation(file_path) as file:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=file)

        elif query.data == 'csv':
            context.user_data['state'] = CSV
            file_path = f"{user_id}_transactions.csv"
            
            # Save the DataFrame to a CSV file
            df.to_csv(file_path, index=False)

            # Send the CSV file
            with safe_file_operation(file_path) as file:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=file)

        elif query.data == 'json':
            context.user_data['state'] = JSON
            file_path = f"{user_id}_transactions.json"
            
            # Save the DataFrame to a JSON file
            df.to_json(file_path, orient='records', force_ascii=False)

            # Send the JSON file
            with safe_file_operation(file_path) as file:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=file)

        elif query.data == 'go_back':
            context.user_data['state'] = NORMAL_PROCESSING
            await query.edit_message_text(text="Вы вернулись в главное меню.")
            return

        context.user_data['state'] = NORMAL_PROCESSING
        await query.edit_message_text(text="Выберите Формат:")

    except Exception as e:
        logger.error(f"Error in button_handler3: {e}")
        await query.edit_message_text(text="Произошла ошибка при экспорте данных. Пожалуйста, попробуйте снова.")
        context.user_data['state'] = NORMAL_PROCESSING

