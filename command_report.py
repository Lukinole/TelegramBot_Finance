import sqlite3
import json
from telegram import Update
from telegram.ext import CallbackContext
from constants import REPORT_DATE_RANGE, NORMAL_PROCESSING
import re
from datetime import datetime
from collections import defaultdict

def get_user_data(user_id):
    conn = sqlite3.connect('user_info.db')
    cursor = conn.cursor()
    cursor.execute('SELECT final_balance, changes FROM user_data WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        final_balance, changes = row
        return {"final_balance": final_balance, "changes": json.loads(changes)}
    else:
        return {"final_balance": 0, "changes": []}

async def report(update: Update, context: CallbackContext) -> None:
    """Отправляет пользователю запрос на ввод периода для отчета."""
    await update.message.reply_text("Введите период в формате YYYY-MM-DD - YYYY-MM-DD")
    context.user_data['state'] = REPORT_DATE_RANGE

async def handle_report_date_range(update: Update, context: CallbackContext) -> None:
    """Handles user input for the report date range."""
    if update.message.text:
        user_input = update.message.text.strip()
        
        # Define a regex pattern for the date range format
        pattern = r'^\d{4}-\d{2}-\d{2}\s*-\s*\d{4}-\d{2}-\d{2}$'
        
        # Check if the input matches the pattern
        if re.match(pattern, user_input):
            # Correctly split the input into start and end dates
            date_parts = user_input.split(' - ')
            
            # Ensure there are exactly two parts
            if len(date_parts) == 2:
                start_date_str, end_date_str = date_parts
                
                # Convert strings to date objects
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                except ValueError:
                    await update.message.reply_text("неверный формат")
                    return
                
                # Fetch transactions from the database
                user_id = str(update.message.from_user.id)
                conn = sqlite3.connect('user_info.db')
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT amount, category, currency FROM transactions
                    WHERE user_id = ? AND date BETWEEN ? AND ?
                ''', (user_id, start_date, end_date))
                transactions = cursor.fetchall()
                conn.close()
                
                # Calculate total income and expenses
                total_income = defaultdict(float)
                total_expenses = defaultdict(float)
                category_totals = defaultdict(lambda: defaultdict(lambda: {'income': 0, 'expenses': 0}))
                
                for amount, category, currency in transactions:
                    if amount > 0:
                        total_income[currency] += amount
                        category_totals[currency][category]['income'] += amount
                    else:
                        total_expenses[currency] += -amount
                        category_totals[currency][category]['expenses'] += -amount
                
                # Prepare the message
                message_lines = []
                for currency in set(total_income.keys()).union(total_expenses.keys()):
                    if total_income[currency] > 0 or total_expenses[currency] > 0:
                        message_lines.append(f"Общие доходы за период ({currency}): {total_income[currency]}")
                        message_lines.append(f"Общие расходы за период ({currency}): {total_expenses[currency]}\n")

                        for category, totals in category_totals[currency].items():
                            if totals['income'] > 0:
                                message_lines.append(f"Доходы в '{category}' ({currency}): {totals['income']}")
                            if totals['expenses'] > 0:
                                message_lines.append(f"Расходы в '{category}' ({currency}): {totals['expenses']}")
                        message_lines.append("")  # Add a blank line for separation
                
                message = "\n".join(message_lines)
                
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("неверный формат")
        else:
            await update.message.reply_text("неверный формат")
    else:
        await update.message.reply_text("неверный формат")
    
    context.user_data['state'] = NORMAL_PROCESSING
