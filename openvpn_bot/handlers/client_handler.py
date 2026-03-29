from telegram import Update
from telegram.ext import ContextTypes
from openvpn_bot.utils.client_manager import get_connected_clients, disconnect_client
from openvpn_bot.utils import validate_username
from openvpn_bot.config import Config

async def clients_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /clients command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    clients = get_connected_clients()
    if not clients:
        await update.message.reply_text('No clients currently connected.')
        return
    
    message = "Currently connected clients:\n\n"
    for client in clients:
        message += (
            f"👤 {client['common_name']}\n"
            f"📍 Real IP: {client['real_address']}\n"
            f"💻 Virtual IP: {client['virtual_address']}\n"
            f"📥 Received: {client['bytes_received'] / (1024**2):.2f} MB\n"
            f"📤 Sent: {client['bytes_sent'] / (1024**2):.2f} MB\n"
            f"⏰ Connected since: {client['connected_since']}\n"
            f"{'-'*30}\n"
        )
    
    await update.message.reply_text(message)

async def client_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /disconnect command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    if not context.args:
        await update.message.reply_text('Please specify a username to disconnect.\nUsage: /disconnect <username>')
        return
    
    username = context.args[0]
    
    # Validate username
    if not validate_username(username):
        await update.message.reply_text(f'❌ Invalid username: {username}')
        return
    
    success, message = disconnect_client(username)
    
    if success:
        await update.message.reply_text(f'✅ {message}')
    else:
        await update.message.reply_text(f'❌ {message}')
