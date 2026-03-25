
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

# Renamed placeholder function to get current month's OpenVPN traffic
async def this_month_ovpn_traffic():
    """Returns placeholder for current month's OpenVPN traffic."""
    return "Используемый трафик OpenVPN за текущий месяц: 100 GB (пока это заглушка)"

# Renamed placeholder function to get last month's OpenVPN traffic
async def last_month_ovpn_traffic():
    """Returns placeholder for last month's OpenVPN traffic."""
    return "Используемый трафик OpenVPN за прошлый месяц: 90 GB (пока это заглушка)"

# Command handler for /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message when the command /start is issued."""
    user = update.effective_user

    # Create a ReplyKeyboardMarkup for the main menu
    reply_keyboard = [[KeyboardButton("OpenVPN")]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)

    await update.message.reply_html(
        f"""Привет, {user.mention_html()}! Я ваш бот для взаимодействия с сервером.
Выберите опцию из меню:""",
        reply_markup=markup
    )

# Handler for the 'OpenVPN' text message, displaying the inline menu
async def openvpn_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the OpenVPN menu with inline buttons."""
    keyboard = [
        [InlineKeyboardButton("Трафик за текущий месяц", callback_data='current_month_traffic')],
        [InlineKeyboardButton("Трафик за прошлый месяц", callback_data='last_month_traffic')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Changed from edit_text back to reply_text for sending a new message
    await update.message.reply_text('Выберите опцию OpenVPN:', reply_markup=reply_markup)

# Callback handler for inline buttons
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    await query.answer() # Acknowledge the callback query

    if query.data == 'current_month_traffic':
        traffic_info = await this_month_ovpn_traffic()
    elif query.data == 'last_month_traffic':
        traffic_info = await last_month_ovpn_traffic()
    else:
        traffic_info = "Неизвестная команда."

    await query.edit_message_text(text=traffic_info)
