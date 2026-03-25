
import logging
import nest_asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import TOKEN
from handlers import start, openvpn_menu, button_callback_handler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main() -> None:
    """Start the bot."""
    # Apply nest_asyncio to allow running asyncio.run() in an already running loop
    nest_asyncio.apply()

    application = Application.builder().token(TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    # Corrected MessageHandler for filtering specific text 'OpenVPN'
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^OpenVPN$'), openvpn_menu))
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # Run the bot until the user presses Ctrl-C
    # We use close_loop=False to avoid issues with Colab's event loop
    application.run_polling(close_loop=False)
    print("Bot started! Send commands to your bot. To stop, you might need to restart the Colab runtime.")

if __name__ == '__main__':
    main()
