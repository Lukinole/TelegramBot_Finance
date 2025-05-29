from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
import sqlite3

# Состояние для ConversationHandler
BROADCAST_MESSAGE = range(1)

# Список разрешенных user_id для использования команды /broadcast
AUTHORIZED_USERS = {"339697024", "111111111"}

async def broadcast_start(update: Update, context: CallbackContext) -> int:
    """Начинает процесс отправки сообщения всем пользователям."""
    user_id = str(update.message.from_user.id)
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("У вас нет прав для использования этой команды.")
        return ConversationHandler.END

    await update.message.reply_text("Введите ваше сообщение для народа:")
    return BROADCAST_MESSAGE

async def broadcast_message(update: Update, context: CallbackContext) -> int:
    """Отправляет сообщение всем пользователям."""
    message_to_send = update.message.text

    try:
        conn = sqlite3.connect('user_info.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM user_data')
        user_ids = cursor.fetchall()
        conn.close()

        for (user_id,) in user_ids:
            try:
                await context.bot.send_message(chat_id=user_id, text=message_to_send)
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

        await update.message.reply_text("Сообщение отправлено всем пользователям.")
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка при отправке сообщения: {e}")

    return ConversationHandler.END
