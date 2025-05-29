from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from constants import NORMAL_PROCESSING, SET_DEFAULT_CURRENCY

async def change_currency(update: Update, context: CallbackContext) -> None:
    """Handles the /change_currency command."""
    # Создаем кнопки
    keyboard = [
        [InlineKeyboardButton("Изменить валюту", callback_data='change_currency')],
        [InlineKeyboardButton("<- назад", callback_data='go_back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с кнопками
    await update.message.reply_text("Выберите опцию:", reply_markup=reply_markup)

async def currency_button_handler(update: Update, context: CallbackContext) -> None:
    """Handles button presses for currency change."""
    query = update.callback_query
    await query.answer()

    if query.data == 'change_currency':
        # Запросить у пользователя ввод новой валюты
        await query.message.reply_text("Пожалуйста, введите новую валюту по умолчанию.")
        context.user_data['state'] = SET_DEFAULT_CURRENCY
    elif query.data == 'go_back':
        context.user_data['state'] = NORMAL_PROCESSING
        await query.message.reply_text("Вы вернулись в главное меню.")
