import json
import sqlite3
import datetime
from constants import NORMAL_PROCESSING, ADD_CATEGORY, DELETE_CATEGORY, EDIT_CATEGORY, EDIT_CATEGORY_NAME
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext


def get_user_data(user_id):
    conn = sqlite3.connect('user_info.db')
    cursor = conn.cursor()
    cursor.execute('SELECT categories FROM user_data WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        categories = json.loads(row[0]) if row[0] else []
        return {
            "categories": categories
        }
    else:
        return {"categories": []}


async def category(update: Update, context: CallbackContext) -> None:
    """Показывает список категорий и кнопки для добавления, удаления и изменения категории."""
    user_id = str(update.message.from_user.id)
    user_data = get_user_data(user_id)
    categories = user_data.get("categories", [])

    categories_text = "\n".join(categories) if categories else "У вас пока нет категорий."
    message = f"Ваши категории:\n{categories_text}\n\nВыберите действие:"

    keyboard = [
        [InlineKeyboardButton("Добавить категорию", callback_data='add_category')],
        [InlineKeyboardButton("Удалить категорию", callback_data='delete_category')],
        [InlineKeyboardButton("Изменить название категории", callback_data='edit_category')],
        [InlineKeyboardButton("<- назад", callback_data='go_back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)

async def button_handler(update: Update, context: CallbackContext) -> None:
    """Обрабатывает нажатие кнопки."""
    query = update.callback_query
    await query.answer()

    if query.data == 'add_category':
        context.user_data['state'] = ADD_CATEGORY
        await query.edit_message_text(text="Введите название категории:")
    elif query.data == 'delete_category':
        context.user_data['state'] = DELETE_CATEGORY
        await query.edit_message_text(text="Введите название категории для удаления:")
    elif query.data == 'edit_category':
        context.user_data['state'] = EDIT_CATEGORY
        await query.edit_message_text(text="Введите старое название категории:")
    elif query.data == 'go_back':
        context.user_data['state'] = NORMAL_PROCESSING
        await query.edit_message_text(text="Вы вернулись в главное меню.")

