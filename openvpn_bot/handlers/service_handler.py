from telegram import Update
from telegram.ext import ContextTypes
from openvpn_bot.utils.openvpn_service import get_service_status, start_service, stop_service, restart_service
from openvpn_bot.config import Config

async def service_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /status command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return

    success, status = get_service_status()
    if not success:
        await update.message.reply_text(f'Error checking OpenVPN service status: {status}')
    else:
        await update.message.reply_text(f'OpenVPN service status: {status}')

async def service_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start_vpn command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    success, message = start_service()
    if success:
        await update.message.reply_text(f'OpenVPN service started successfully: {message}')
    else:
        await update.message.reply_text(f'Error starting OpenVPN service: {message}')

async def service_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /stop_vpn command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    success, message = stop_service()
    if success:
        await update.message.reply_text(f'OpenVPN service stopped successfully: {message}')
    else:
        await update.message.reply_text(f'Error stopping OpenVPN service: {message}')

async def service_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /restart_vpn command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    success, message = restart_service()
    if success:
        await update.message.reply_text(f'OpenVPN service restarted successfully: {message}')
    else:
        await update.message.reply_text(f'Error restarting OpenVPN service: {message}')
