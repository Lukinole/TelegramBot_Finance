import sqlite3
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from constants import EDIT_FOR_FILTER, NORMAL_PROCESSING, NEW_TRANSACTION_DATA
import logging
import openai
import os

logger = logging.getLogger(__name__)

# Set up OpenAI API key
API_KEY = os.getenv("API_KEY")
openai.api_key = API_KEY

async def edit(update: Update, context: CallbackContext) -> None:
    """Handles the /edit command to prompt for text input and then list all transactions."""
    context.user_data['state'] = EDIT_FOR_FILTER
    await update.message.reply_text(
        'Введите фильтр для поиска через запятую или тире. Например:\n'
        '"2025-02-20",\n'
        '"2025-02-20 - 2025-02-25",\n'
        '"Продукты, коммуналка",\n'
        '"1000 - 2000",\n'
        '"2025-02-20 - 2025-02-25, Продукты, коммуналка, 1000 - 2000"'
    )

async def process_filter(update: Update, context: CallbackContext) -> None:
    """Processes the user input for filtering transactions."""
    user_id = str(update.message.from_user.id)
    user_message = update.message.text.strip()

    # Patterns for single date, date range, list of dates, single amount, amount range, list of amounts, and list of categories
    single_date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    date_range_pattern = r'^\d{4}-\d{2}-\d{2}\s*-\s*\d{4}-\d{2}-\d{2}$'
    single_amount_pattern = r'^-?\d+$'
    amount_range_pattern = r'^(-?\d+)\s*[-–]\s*(-?\d+)$'
    category_pattern = r'^\w+$'

    # Split the user message by commas to handle multiple filters
    filters = [f.strip() for f in user_message.split(',')]

    # Base query
    query = 'SELECT id, amount, date, category, currency FROM transactions WHERE user_id = ?'
    params = [user_id]

    # Process each filter
    for f in filters:
        if re.match(single_date_pattern, f):
            query += ' AND date = ?'
            params.append(f)
        elif re.match(date_range_pattern, f):
            # Split the string by the third hyphen
            parts = f.split(' - ', 1)
            if len(parts) == 2:
                start_date, end_date = parts
                logger.info(f"Date range extracted: start_date={start_date.strip()}, end_date={end_date.strip()}")
                query += ' AND date BETWEEN ? AND ?'
                params.extend([start_date.strip(), end_date.strip()])  # Ensure no leading/trailing spaces
            else:
                await update.message.reply_text("Неверный формат диапазона дат.")
                context.user_data['state'] = NORMAL_PROCESSING
                return
        elif re.match(single_amount_pattern, f):
            query += ' AND amount = ?'
            params.append(int(f))
        elif re.match(amount_range_pattern, f):
            start_amount, end_amount = map(int, re.match(amount_range_pattern, f).groups())
            query += ' AND amount BETWEEN ? AND ?'
            params.extend([start_amount, end_amount])
        elif re.match(category_pattern, f):
            query += ' AND category = ?'
            params.append(f)
        else:
            await update.message.reply_text("Вы указали неверные данные.")
            context.user_data['state'] = NORMAL_PROCESSING
            return

    # Execute the query
    conn = sqlite3.connect('user_info.db')
    cursor = conn.cursor()
    logger.info(f"Executing query: {query} with params: {params}")
    cursor.execute(query, params)
    transactions = cursor.fetchall()
    conn.close()

    # Prepare the message with buttons
    if transactions:
        keyboard = []
        transaction_details_text = []  # Create a list to store transaction details as text
        for transaction in transactions:
            transaction_id, amount, date, category, currency = transaction
            button_text = f"{date}: {amount} {currency} ({category})"
            callback_data = f"transaction_{transaction_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            # Save transaction details as text
            context.user_data[callback_data] = f"ID: {transaction_id}, Date: {date}, Amount: {amount}, Category: {category}, Currency: {currency}"
            transaction_details_text.append(f"ID: {transaction_id}, Date: {date}, Amount: {amount}, Category: {category}, Currency: {currency}")

        # Save the text representation of transaction details in context
        context.user_data['transaction_details_text'] = transaction_details_text

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Ваши транзакции:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("У вас нет транзакций за указанный период или суммы.")

    context.user_data['state'] = NORMAL_PROCESSING  # Reset state after processing

async def send_action_buttons(update: Update, context: CallbackContext) -> None:
    """Sends action buttons if transaction details are available."""
    transaction_details = context.user_data.get('selected_transaction')
    
    if transaction_details:
        # Create buttons
        keyboard = [
            [InlineKeyboardButton("Изменить транзакцию", callback_data="edit_transaction")],
            [InlineKeyboardButton("Удалить транзакцию", callback_data="delete_transaction")],
            [InlineKeyboardButton("<- Назад", callback_data="back_to_transactions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send message with action buttons
        await update.effective_chat.send_message("Выберите действие:", reply_markup=reply_markup)

async def button_handler2(update: Update, context: CallbackContext) -> None:
    """Handles button presses for transaction actions."""
    query = update.callback_query
    await query.answer()

    # Log the callback data
    logger.info(f"Callback data received: {query.data}")

    # Directly use the saved transaction details text
    transaction_details_text = context.user_data.get('transaction_details_text')
    if transaction_details_text:
        # Log the transaction details text
        logger.info(f"Transaction details text: {transaction_details_text}")

        # Check which button was pressed and respond accordingly
        if query.data == "edit_transaction":
            selected_transaction = context.user_data.get('selected_transaction')
            context.user_data['state'] = NEW_TRANSACTION_DATA
            await query.edit_message_text(text=f"напишите, что вы хотите изменить {selected_transaction}")
        elif query.data == "delete_transaction":
            selected_transaction = context.user_data.get('selected_transaction')
            if selected_transaction:
                transaction_id = selected_transaction.split(', ')[0].split(': ')[1]
                conn = sqlite3.connect('user_info.db')
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
                conn.commit()
                conn.close()
                context.user_data['state'] = NORMAL_PROCESSING
                await query.edit_message_text(text=f"Транзакция {selected_transaction} удалена.")
            else:
                await query.edit_message_text(text="Не удалось найти транзакцию для удаления.")
        elif query.data == "back_to_transactions":
            context.user_data['state'] = NORMAL_PROCESSING
            await query.edit_message_text(text="Вы вернулись в главное меню.")
        else:
            transaction_id = query.data.split('_')[1] if '_' in query.data else None
            selected_transaction = next(
                (details for details in transaction_details_text if f"ID: {transaction_id}" in details),
                None
            )
            if selected_transaction:
                context.user_data['selected_transaction'] = selected_transaction
                context.user_data['state'] = NORMAL_PROCESSING
                await query.edit_message_text(text=f"Транзакция выбрана: {selected_transaction}")
                await send_action_buttons(update, context)
            else:
                logger.warning("Specific transaction details not found.")
                await query.edit_message_text(text="Детали транзакции не найдены.")
    else:
        logger.warning("Transaction details not found.")
        context.user_data['state'] = NORMAL_PROCESSING
        await query.edit_message_text(text="Детали транзакции не найдены.")

async def process_new_transaction_data(update: Update, context: CallbackContext) -> None:
    """Processes new transaction data input by the user."""
    user_input = update.message.text
    selected_transaction = context.user_data.get('selected_transaction')
    transaction_id = selected_transaction.split(', ')[0].split(': ')[1]
    user_id = str(update.message.from_user.id)  # Получаем user_id

    # Use OpenAI API to process the input
    try:
        API_KEY = os.getenv("API_KEY")
        openai.api_key = API_KEY
        client = openai.OpenAI(api_key=API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"""You are a helpful assistant. 
                 Format the user's transaction data for database insertion. 
                 The user will provide new transaction details.
                 Old transaction data: {selected_transaction}, use information from old transaction data if user will not provide some new information (for example if user want change just date use old information about amount, category, and currency).
                 Return strictly the data in the format: 'Date: YYYY-MM-DD, Amount: 100, Category: Example, Currency: USD'."""},
                {"role": "user", "content": user_input}
            ]
        )
        formatted_data = response.choices[0].message.content.strip()

        # Ensure the formatted data is in the correct format
        try:
            # Split the formatted data and extract values
            parts = formatted_data.split(', ')
            if len(parts) != 4:
                raise ValueError("Incorrect format received from AI.")

            date, amount, category, currency = [part.split(': ')[1] for part in parts]
            
            # Check for empty values and handle them
            if not date or not amount or not category or not currency:
                raise ValueError("One of the fields is empty.")

            # Delete the old transaction and insert the new one
            conn = sqlite3.connect('user_info.db')
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
            cursor.execute(
                "INSERT INTO transactions (id, user_id, date, amount, category, currency) VALUES (?, ?, ?, ?, ?, ?)",
                (transaction_id, user_id, date, int(amount), category, currency)
            )
            conn.commit()
            conn.close()
            await update.message.reply_text(f"Транзакция \n\n{selected_transaction} \n\nуспешно обновлена на \n\n{formatted_data}.")
        except ValueError as ve:
            logger.error(f"Value error: {ve}")
            await update.message.reply_text("Ошибка в формате данных. Пожалуйста, проверьте ввод.")
    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении транзакции.")

    # Reset state to NORMAL_PROCESSING
    context.user_data['state'] = NORMAL_PROCESSING

