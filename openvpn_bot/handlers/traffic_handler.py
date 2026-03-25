from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from openvpn_bot.utils.traffic_monitor import get_current_month_traffic, get_user_traffic, get_top_users, check_traffic_thresholds
from openvpn_bot.config import Config

async def traffic_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /traffic command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    # Get overall traffic for the current month
    total_bytes = get_current_month_traffic()
    total_gb = total_bytes / (1024 ** 3)
    
    # Get top 5 users
    top_users = get_top_users(5)
    
    message = f"📊 Traffic Statistics for {datetime.now().strftime('%B %Y')}:\n\n"
    message += f"📈 Total traffic: {total_gb:.2f} GB\n\n"
    message += "🏆 Top 5 users:\n"
    for i, user in enumerate(top_users, 1):
        message += f"{i}. {user['user']}: {user['total'] / (1024**3):.2f} GB\n"
    
    await update.message.reply_text(message)

async def user_traffic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /user_traffic command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    if not context.args:
        await update.message.reply_text('Please specify a username.\nUsage: /user_traffic <username>')
        return
    
    username = context.args[0]
    traffic = get_user_traffic(username)
    
    message = f"📊 Traffic for user {username}:\n\n"
    message += f"📥 Received: {traffic['received'] / (1024**3):.2f} GB\n"
    message += f"📤 Sent: {traffic['sent'] / (1024**3):.2f} GB\n"
    message += f"📊 Total: {traffic['total'] / (1024**3):.2f} GB\n"
    
    await update.message.reply_text(message)

async def traffic_thresholds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /throttle command to check thresholds."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    threshold_data = check_traffic_thresholds()
    
    message = f"🚦 Traffic Thresholds:\n\n"
    message += f"📈 Current month traffic: {threshold_data['total_gb']:.2f} GB\n\n"
    message += "🔔 Notification thresholds (GB):\n"
    for threshold in threshold_data['all_thresholds']:
        status = "✅ Crossed" if threshold in threshold_data['crossed_thresholds'] else "❌ Not crossed"
        message += f"  {threshold} GB: {status}\n"
    
    if threshold_data['crossed_thresholds']:
        message += "\n🚨 Alert: You have crossed the following thresholds: "
        message += ", ".join(map(str, threshold_data['crossed_thresholds'])) + " GB"
    else:
        message += "\n✅ All thresholds are within limits."
    
    await update.message.reply_text(message)
