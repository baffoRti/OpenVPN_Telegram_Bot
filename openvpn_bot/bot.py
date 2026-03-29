import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.error import TelegramError

from openvpn_bot.config import Config
from openvpn_bot.handlers.service_handler import (
    service_status, service_start, service_stop, service_restart
)
from openvpn_bot.handlers.client_handler import clients_list, client_disconnect
from openvpn_bot.handlers.traffic_handler import (
    traffic_stats, user_traffic, traffic_thresholds, traffic_check, reset_traffic_notifications
)
from openvpn_bot.handlers.cert_handler import (
    cert_list, cert_generate, cert_revoke, cert_renew, cert_ban, cert_unban
)
from openvpn_bot.utils.cert_manager import check_cert_banned
from openvpn_bot.utils import validate_username
from openvpn_bot.utils.traffic_notifier import check_and_notify

# Help text constant
HELP_TEXT = """
Available commands:
/start - Show the main menu
/help - Show this help message
/status - Check OpenVPN service status
/start_vpn - Start OpenVPN service
/stop_vpn - Stop OpenVPN service
/restart_vpn - Restart OpenVPN service
/clients - List connected clients
/disconnect <username> - Disconnect a client
/traffic - Show traffic statistics
/user_traffic <username> - Show traffic for specific user
/throttle - Show traffic thresholds and current usage
/traffic_check - Manually check traffic thresholds and send notifications
/reset_traffic_alerts - Reset traffic notification state
/cert_list - List certificates
/cert_generate <common_name> - Generate a certificate
/cert_revoke <common_name> - Revoke a certificate
/cert_renew <common_name> - Renew a certificate
/cert_ban <common_name> - Ban a certificate (block access without revoking)
/cert_unban <common_name> - Unban a certificate (restore access)
"""

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    """Check if the user is an admin."""
    return user_id in Config.ADMIN_IDS

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Create the main menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🖥️ Service Control", callback_data="service_menu"),
            InlineKeyboardButton("👥 List Clients", callback_data="client_list"),
        ],
        [
            InlineKeyboardButton("📊 Traffic Stats", callback_data="traffic_stats"),
            InlineKeyboardButton("🔐 List Certificates", callback_data="cert_list"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def main_menu_back_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard with a back to main menu button."""
    keyboard = [
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def bottom_keyboard() -> ReplyKeyboardMarkup:
    """Create a persistent keyboard at the bottom of the chat."""
    keyboard = [[KeyboardButton("Start")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


def service_menu_keyboard() -> InlineKeyboardMarkup:
    """Create the service control submenu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🔍 Status", callback_data="service_status"),
            InlineKeyboardButton("▶️ Start", callback_data="service_start"),
        ],
        [
            InlineKeyboardButton("⏹️ Stop", callback_data="service_stop"),
            InlineKeyboardButton("🔄 Restart", callback_data="service_restart"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def service_action_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard with back to service menu after an action."""
    keyboard = [
        [
            InlineKeyboardButton("🔙 Back to Service Menu", callback_data="service_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with the main menu when the command /start is issued."""
    if not update.effective_user:
        return
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text('You are not authorized to use this bot.')
        return
    if update.message:
        await update.message.reply_text(
            f'Hi {user.first_name}! I am your OpenVPN management bot.\n'
            f'Please select an action from the menu below:',
            reply_markup=bottom_keyboard()
        )
        await update.message.reply_text(
            'Main Menu:',
            reply_markup=main_menu_keyboard()
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    if not update.effective_user:
        return
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text('You are not authorized to use this bot.')
        return
    if update.message:
        await update.message.reply_text(HELP_TEXT)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses from the main menu."""
    query = update.callback_query
    # Answer the callback query to remove the loading state
    await query.answer()

    # Check if the user is an admin
    if query.from_user is None or not is_admin(query.from_user.id):
        if query.message is not None:
            await query.edit_message_text(text="You are not authorized to use this bot.")
        return

    # Get the data from the button press
    data = query.data

    # We'll handle each button press by calling the appropriate function and then editing the message
    try:
        if data == "main_menu":
            # Show main menu
            if query.message is not None:
                await query.edit_message_text(
                    text='Please select an action from the menu below:',
                    reply_markup=main_menu_keyboard()
                )

        elif data == "service_menu":
            # Show service control submenu
            if query.message is not None:
                await query.edit_message_text(
                    text=(
                        "🖥️ OpenVPN Service Control\n\n"
                        "Manage the OpenVPN server process.\n"
                        "Use the buttons below to check status, start, stop, or restart the service."
                    ),
                    reply_markup=service_menu_keyboard()
                )

        elif data == "service_status":
            # Handle service status
            from openvpn_bot.utils.openvpn_service import get_service_status
            success, result = get_service_status()
            if not success:
                if query.message is not None:
                    await query.edit_message_text(
                        text=(
                            f"🔴 OpenVPN Status: {result.upper()}\n\n"
                            f"The VPN server is not running. Use Start to launch it."
                        ),
                        reply_markup=service_action_keyboard()
                    )
            else:
                if query.message is not None:
                    await query.edit_message_text(
                        text=(
                            f"🟢 OpenVPN Status: {result.upper()}\n\n"
                            f"The VPN server is running and accepting connections."
                        ),
                        reply_markup=service_action_keyboard()
                    )

        elif data == "service_start":
            # Handle service start
            from openvpn_bot.utils.openvpn_service import start_service
            success, message = start_service()
            if success:
                if query.message is not None:
                    await query.edit_message_text(
                        text=(
                            "✅ OpenVPN Service Started\n\n"
                            "The VPN server is now running.\n"
                            "Clients can connect using their .ovpn configuration files."
                        ),
                        reply_markup=service_action_keyboard()
                    )
            else:
                if query.message is not None:
                    await query.edit_message_text(
                        text=(
                            f"❌ Failed to Start OpenVPN\n\n"
                            f"Error: {message}\n\n"
                            f"Check server logs for details: journalctl -u openvpn"
                        ),
                        reply_markup=service_action_keyboard()
                    )

        elif data == "service_stop":
            # Handle service stop
            from openvpn_bot.utils.openvpn_service import stop_service
            success, message = stop_service()
            if success:
                if query.message is not None:
                    await query.edit_message_text(
                        text=(
                            "⏹️ OpenVPN Service Stopped\n\n"
                            "The VPN server has been shut down.\n"
                            "All active client connections have been terminated."
                        ),
                        reply_markup=service_action_keyboard()
                    )
            else:
                if query.message is not None:
                    await query.edit_message_text(
                        text=(
                            f"❌ Failed to Stop OpenVPN\n\n"
                            f"Error: {message}\n\n"
                            f"Check server logs for details: journalctl -u openvpn"
                        ),
                        reply_markup=service_action_keyboard()
                    )

        elif data == "service_restart":
            # Handle service restart
            from openvpn_bot.utils.openvpn_service import restart_service
            success, message = restart_service()
            if success:
                if query.message is not None:
                    await query.edit_message_text(
                        text=(
                            "🔄 OpenVPN Service Restarted\n\n"
                            "The VPN server has been restarted.\n"
                            "All previous connections were dropped.\n"
                            "Clients will need to reconnect."
                        ),
                        reply_markup=service_action_keyboard()
                    )
            else:
                if query.message is not None:
                    await query.edit_message_text(
                        text=(
                            f"❌ Failed to Restart OpenVPN\n\n"
                            f"Error: {message}\n\n"
                            f"Check server logs for details: journalctl -u openvpn"
                        ),
                        reply_markup=service_action_keyboard()
                    )

        elif data == "client_list":
            from openvpn_bot.utils.client_manager import get_connected_clients
            clients = get_connected_clients()
            if not clients:
                if query.message is not None:
                    await query.edit_message_text(
                        text='No clients currently connected.',
                        reply_markup=main_menu_back_keyboard()
                    )
                return
            
            # Build message with disconnect buttons for each client
            if query.message is not None:
                text = "Currently connected clients:\n\n"
                keyboard = []
                
                for client in clients:
                    text += f"👤 {client['common_name']}\n"
                    text += f"📍 {client['real_address']}\n"
                    if client.get('virtual_address'):
                        text += f"💻 Virtual IP: {client['virtual_address']}\n"
                    text += (
                        f"📥 {client['bytes_received'] / (1024**2):.2f} MB received\n"
                        f"📤 {client['bytes_sent'] / (1024**2):.2f} MB sent\n"
                        f"⏰ Connected {client.get('connected_since_display', client['connected_since'])}\n"
                    )
                    
                    # Add disconnect button for this client
                    keyboard.append([
                        InlineKeyboardButton(
                            f"❌ Disconnect {client['common_name']}", 
                            callback_data=f"client_disconnect:{client['common_name']}"
                        )
                    ])
                    
                    text += "-"*30 + "\n\n"
                
                # Add back button
                keyboard.append([
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text=text, reply_markup=reply_markup)

        elif data.startswith("client_disconnect:"):
            # Handle client disconnect
            if data is None:
                return
            username = data.split(":", 1)[1]  # Extract username after "client_disconnect:"
            
            # Validate username
            if not validate_username(username):
                if query.message is not None:
                    await query.edit_message_text(
                        text=f'❌ Invalid username: {username}',
                        reply_markup=main_menu_back_keyboard()
                    )
                return
            
            # Ask for confirmation before disconnecting
            if query.message is not None:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Yes, Disconnect", callback_data=f"confirm_disconnect:{username}"),
                        InlineKeyboardButton("❠ Cancel", callback_data="client_list")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text=f'Are you sure you want to disconnect client "{username}"?\nThis action cannot be undone.',
                    reply_markup=reply_markup
                )

        elif data.startswith("confirm_disconnect:"):
            # Handle confirmed client disconnect
            if data is None:
                return
            username = data.split(":", 1)[1]  # Extract username after "confirm_disconnect:"
            
            # Validate username
            if not validate_username(username):
                if query.message is not None:
                    await query.edit_message_text(
                        text=f'❌ Invalid username: {username}',
                        reply_markup=main_menu_back_keyboard()
                    )
                return
            
            from openvpn_bot.utils.client_manager import disconnect_client
            success, message = disconnect_client(username)
            
            if success:
                if query.message is not None:
                    await query.edit_message_text(
                        text=f'✅ {message}',
                        reply_markup=main_menu_back_keyboard()
                    )
            else:
                if query.message is not None:
                    await query.edit_message_text(
                        text=f'❌ {message}',
                        reply_markup=main_menu_back_keyboard()
                    )

        elif data == "traffic_stats":
            # Check if traffic monitor is available
            if not Config.TRAFFIC_MONITOR_AVAILABLE:
                if query.message is not None:
                    await query.edit_message_text(
                        text=Config.get_traffic_monitor_help_message(),
                        reply_markup=main_menu_back_keyboard()
                    )
                return
            
            from openvpn_bot.utils.traffic_monitor import get_current_month_traffic, get_top_users
            total_bytes = get_current_month_traffic()
            total_gb = total_bytes / (1024 ** 3)
            top_users = get_top_users(5)
            month_name = datetime.now().strftime('%B %Y')
            message_lines = [
                f"📊 Traffic Statistics for {month_name}:\n",
                f"📈 Total traffic: {total_gb:.2f} GB\n",
                "\n🏆 Top 5 users:\n"
            ]
            for i, user in enumerate(top_users, 1):
                message_lines.append(f"{i}. {user['user']}: {user['total'] / (1024**3):.2f} GB\n")
            if query.message is not None:
                keyboard = [
                    [
                        InlineKeyboardButton("👥 Full User List", callback_data="traffic_all_users"),
                        InlineKeyboardButton("📅 Last Month", callback_data="traffic_last_month"),
                    ],
                    [
                        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")
                    ]
                ]
                await query.edit_message_text(
                    text=''.join(message_lines),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        elif data == "traffic_all_users":
            # Check if traffic monitor is available
            if not Config.TRAFFIC_MONITOR_AVAILABLE:
                if query.message is not None:
                    await query.edit_message_text(
                        text=Config.get_traffic_monitor_help_message(),
                        reply_markup=main_menu_back_keyboard()
                    )
                return
            
            from openvpn_bot.utils.traffic_monitor import get_current_month_traffic, get_all_users_traffic
            current_month = datetime.now().strftime('%Y-%m')
            total_bytes = get_current_month_traffic()
            total_gb = total_bytes / (1024 ** 3)
            users = get_all_users_traffic(current_month)
            month_name = datetime.now().strftime('%B %Y')

            message_lines = [
                f"👥 All Users Traffic for {month_name}:\n",
                f"📈 Total: {total_gb:.2f} GB\n\n"
            ]
            if users:
                for i, user in enumerate(users, 1):
                    message_lines.append(
                        f"{i}. {user['user']}: {user['total'] / (1024**3):.2f} GB "
                        f"(↓{user['received'] / (1024**3):.2f} ↑{user['sent'] / (1024**3):.2f})\n"
                    )
            else:
                message_lines.append("No data available.\n")

            text = ''.join(message_lines)
            if len(text) > 4000:
                text = text[:3990] + "\n..."

            if query.message is not None:
                await query.edit_message_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back to Traffic Stats", callback_data="traffic_stats")
                    ]])
                )

        elif data == "traffic_last_month":
            # Check if traffic monitor is available
            if not Config.TRAFFIC_MONITOR_AVAILABLE:
                if query.message is not None:
                    await query.edit_message_text(
                        text=Config.get_traffic_monitor_help_message(),
                        reply_markup=main_menu_back_keyboard()
                    )
                return
            
            from openvpn_bot.utils.traffic_monitor import get_month_traffic, get_all_users_traffic, get_last_month_str
            last_month = get_last_month_str()
            total_bytes = get_month_traffic(last_month)
            total_gb = total_bytes / (1024 ** 3)
            users = get_all_users_traffic(last_month)
            month_name = datetime.strptime(last_month, '%Y-%m').strftime('%B %Y')

            message_lines = [
                f"📅 Traffic Statistics for {month_name}:\n",
                f"📈 Total traffic: {total_gb:.2f} GB\n\n"
            ]
            if users:
                message_lines.append("👥 All users:\n\n")
                for i, user in enumerate(users, 1):
                    message_lines.append(
                        f"{i}. {user['user']}: {user['total'] / (1024**3):.2f} GB "
                        f"(↓{user['received'] / (1024**3):.2f} ↑{user['sent'] / (1024**3):.2f})\n"
                    )
            else:
                message_lines.append("No data available for this month.\n")

            text = ''.join(message_lines)
            if len(text) > 4000:
                text = text[:3990] + "\n..."

            if query.message is not None:
                await query.edit_message_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back to Traffic Stats", callback_data="traffic_stats")
                    ]])
                )

        elif data == "cert_list" or data.startswith("cert_list:"):
            from openvpn_bot.utils.cert_manager import list_all_certificates
            success, message = list_all_certificates()

            # Parse page number from callback data
            page = 0
            if ":" in data:
                try:
                    page = int(data.split(":", 1)[1])
                except ValueError:
                    page = 0

            if success:
                if query.message is not None:
                    lines = [l.strip() for l in message.strip().split('\n') if l.strip()]
                    total = len(lines)
                    
                    if total == 0:
                        # No certificates - show simple message with generate button
                        await query.edit_message_text(
                            text='📋 No certificates yet.',
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("➕ Generate New Certificate", callback_data="cert_generate_prompt")],
                                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
                            ])
                        )
                        return
                    
                    per_page = 10
                    total_pages = max(1, (total + per_page - 1) // per_page)
                    page = max(0, min(page, total_pages - 1))
                    start = page * per_page
                    end = min(start + per_page, total)
                    page_certs = lines[start:end]

                    title = f"📋 Certificates ({total} total, page {page + 1}/{total_pages}):"

                    keyboard = []
                    for cert_name in page_certs:
                        keyboard.append([
                            InlineKeyboardButton(
                                f"🔐 {cert_name}",
                                callback_data=f"cert_action:{cert_name}"
                            )
                        ])

                    # Pagination row
                    nav_row = []
                    if page > 0:
                        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cert_list:{page - 1}"))
                    if page < total_pages - 1:
                        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"cert_list:{page + 1}"))
                    if nav_row:
                        keyboard.append(nav_row)

                    # Action buttons
                    keyboard.append([
                        InlineKeyboardButton("➕ Generate New", callback_data="cert_generate_prompt"),
                        InlineKeyboardButton("🔄 Refresh", callback_data=f"cert_list:{page}")
                    ])
                    keyboard.append([
                        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")
                    ])

                    reply_markup = InlineKeyboardMarkup(keyboard)
                    try:
                        await query.edit_message_text(
                            text=title,
                            reply_markup=reply_markup
                        )
                    except TelegramError as e:
                        if "Message is not modified" in str(e):
                            await query.answer("List is up to date")
                        else:
                            raise
            else:
                if query.message is not None:
                    await query.edit_message_text(
                        text=f'❌ Error listing certificates: {message}',
                        reply_markup=main_menu_back_keyboard()
                    )

        elif data.startswith("cert_action:"):
            # Handle certificate action selection
            if data is None:
                return
            cert_name = data.split(":", 1)[1]  # Extract certificate name after "cert_action:"
            
            # Strip all prefixes to get clean certificate name
            # Format can be: "[BANNED] Test", "BANNED_Test", or just "Test"
            clean_name = cert_name
            clean_name = clean_name.replace("[BANNED] ", "").replace("[BANNED]", "")
            clean_name = clean_name.replace("BANNED_", "")
            clean_name = clean_name.strip()
            
            # Check if certificate is banned
            is_banned, _ = check_cert_banned(clean_name)
            
            # Build keyboard based on ban status
            if query.message is not None:
                keyboard = [
                    [
                        InlineKeyboardButton("📥 Download Config", callback_data=f"cert_download:{clean_name}")
                    ],
                    [
                        InlineKeyboardButton("❌ Revoke", callback_data=f"cert_revoke:{clean_name}"),
                        InlineKeyboardButton("🔄 Renew", callback_data=f"cert_renew:{clean_name}")
                    ]
                ]
                
                # Add Ban or Unban button based on status
                if is_banned:
                    keyboard.append([
                        InlineKeyboardButton("✅ Unban", callback_data=f"cert_unban:{clean_name}")
                    ])
                    status_text = "🚫 Banned"
                else:
                    keyboard.append([
                        InlineKeyboardButton("🚫 Ban", callback_data=f"cert_ban:{clean_name}")
                    ])
                    status_text = "✅ Active"
                
                keyboard.append([
                    InlineKeyboardButton("🔙 Back to Certificate List", callback_data="cert_list")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text=f'Certificate: {clean_name}\nStatus: {status_text}',
                    reply_markup=reply_markup
                )

        elif data.startswith("cert_download:"):
            # Send .ovpn config file to the user
            if data is None:
                return
            cert_name = data.split(":", 1)[1]
            
            # Strip [BANNED] prefix if present
            cert_name = cert_name.replace("[BANNED] ", "").replace("[BANNED]", "").strip()
            
            ovpn_path = os.path.join(Config.OPENVPN_CERT_DIR, f"{cert_name}.ovpn")

            if not os.path.exists(ovpn_path):
                await query.answer(f"Config file for {cert_name} not found on server")
                return

            try:
                with open(ovpn_path, 'rb') as f:
                    await query.message.reply_document(
                        document=f,
                        filename=f"{cert_name}.ovpn",
                        caption=f"🔐 OpenVPN config for {cert_name}"
                    )
                await query.answer("Config sent")
            except Exception as e:
                logger.error(f"Error sending .ovpn file: {e}")
                await query.answer(f"Error: {str(e)}")

        elif data.startswith("cert_revoke:") or data.startswith("cert_renew:"):
            # Handle certificate revoke/renew
            if data is None:
                return
            parts = data.split(":", 2)  # Split into [action, cert_name]
            action = parts[0]  # "cert_revoke" or "cert_renew"
            cert_name = parts[1]  # certificate name
            
            # Strip [BANNED] prefix if present
            cert_name = cert_name.replace("[BANNED] ", "").replace("[BANNED]", "").strip()
            
            # Ask for confirmation
            action_text = "revoke" if action == "cert_revoke" else "renew"
            confirm_action = "confirm_revoke" if action == "cert_revoke" else "confirm_renew"
            if query.message is not None:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Yes, " + action_text.title(), callback_data=f"{confirm_action}:{cert_name}"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"cert_action:{cert_name}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text=f'Are you sure you want to {action_text} certificate "{cert_name}"?\nThis action cannot be undone.',
                    reply_markup=reply_markup
                )

        elif data.startswith("confirm_revoke:") or data.startswith("confirm_renew:"):
            # Handle confirmed certificate revoke/renew
            if data is None:
                return
            parts = data.split(":", 1)
            if len(parts) < 2:
                if query.message is not None:
                    await query.edit_message_text(text="Invalid callback data")
                return

            action = parts[0]   # "confirm_revoke" or "confirm_renew"
            cert_name = parts[1]
            
            # Strip [BANNED] prefix if present
            cert_name = cert_name.replace("[BANNED] ", "").replace("[BANNED]", "").strip()

            # Import the appropriate function
            from openvpn_bot.utils.cert_manager import revoke_certificate, renew_certificate

            # Call the appropriate function
            if action == "confirm_revoke":
                success, message = revoke_certificate(cert_name)
                action_text = "revoked"
                success_msg = f'✅ Certificate revoked: {cert_name}'
                error_msg = f'❌ Failed to revoke certificate: {message}'
            else:  # confirm_renew
                success, message = renew_certificate(cert_name)
                action_text = "renewed"
                success_msg = f'✅ Certificate renewed: {cert_name}'
                error_msg = f'❌ Failed to renew certificate: {message}'
            
            if success:
                if query.message is not None:
                    await query.edit_message_text(
                        text=success_msg,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Back to Certificate List", callback_data="cert_list")
                        ]])
                    )
            else:
                if query.message is not None:
                    await query.edit_message_text(
                        text=error_msg,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Back to Certificate List", callback_data="cert_list")
                        ]])
                    )

        elif data.startswith("cert_ban:") or data.startswith("cert_unban:"):
            # Handle certificate ban/unban request
            if data is None:
                return
            parts = data.split(":", 2)
            action = parts[0]  # "cert_ban" or "cert_unban"
            cert_name = parts[1]
            
            # Strip [BANNED] prefix if present
            cert_name = cert_name.replace("[BANNED] ", "").replace("[BANNED]", "").strip()
            
            # Ask for confirmation
            action_text = "ban" if action == "cert_ban" else "unban"
            confirm_action = "confirm_ban" if action == "cert_ban" else "confirm_unban"
            action_emoji = "🚫" if action == "cert_ban" else "✅"
            
            if query.message is not None:
                keyboard = [
                    [
                        InlineKeyboardButton(f"{action_emoji} Yes, {action_text.title()}", callback_data=f"{confirm_action}:{cert_name}"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"cert_action:{cert_name}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text=f'Are you sure you want to {action_text} certificate "{cert_name}"?',
                    reply_markup=reply_markup
                )

        elif data.startswith("confirm_ban:") or data.startswith("confirm_unban:"):
            # Handle confirmed certificate ban/unban
            if data is None:
                return
            parts = data.split(":", 1)
            if len(parts) < 2:
                if query.message is not None:
                    await query.edit_message_text(text="Invalid callback data")
                return

            action = parts[0]   # "confirm_ban" or "confirm_unban"
            cert_name = parts[1]
            
            # Strip [BANNED] prefix if present
            cert_name = cert_name.replace("[BANNED] ", "").replace("[BANNED]", "").strip()

            # Import the appropriate function
            from openvpn_bot.utils.cert_manager import ban_certificate, unban_certificate

            # Call the appropriate function
            if action == "confirm_ban":
                success, message = ban_certificate(cert_name)
                action_text = "ban"
                success_msg = f'✅ Certificate banned: {cert_name}'
                error_msg = f'❌ Failed to ban certificate: {message}'
            else:  # confirm_unban
                success, message = unban_certificate(cert_name)
                action_text = "unban"
                success_msg = f'✅ Certificate unbanned: {cert_name}'
                error_msg = f'❌ Failed to unban certificate: {message}'
            
            if success:
                if query.message is not None:
                    await query.edit_message_text(
                        text=success_msg,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Back to Certificate List", callback_data="cert_list")
                        ]])
                    )
            else:
                if query.message is not None:
                    await query.edit_message_text(
                        text=error_msg,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Back to Certificate List", callback_data="cert_list")
                        ]])
                    )

        elif data == "cert_generate_prompt":
            # Prompt for certificate generation
            if query.message is not None:
                await query.edit_message_text(
                    text='Please enter the common name for the new certificate:',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back to Certificate List", callback_data="cert_list")
                    ]])
                )
                # Set user state to expect certificate name input
                if context.user_data is not None:
                    context.user_data['awaiting_cert_name'] = True
                else:
                    # Fallback if user_data is somehow None
                    logger.warning("context.user_data is None in cert_generate_prompt")

        elif data == "help":
            if query.message is not None:
                await query.edit_message_text(text=HELP_TEXT)

        else:
            if query.message is not None:
                await query.edit_message_text(text="Unknown action.")

    except Exception as e:
        logger.error(f"Error in button callback: {e}")
        if query.message is not None:
            await query.edit_message_text(text=f"An error occurred: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages, particularly for certificate generation input."""
    if update.effective_user is None or update.message is None:
        return
    
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text('You are not authorized to use this bot.')
        return

    # Handle bottom keyboard "Start" button
    message_text = update.message.text.strip() if update.message.text else ""
    if message_text == "Start":
        await update.message.reply_text(
            'Main Menu:',
            reply_markup=main_menu_keyboard()
        )
        return
    
    # Check if we're expecting a certificate name
    if context.user_data is not None and context.user_data.get('awaiting_cert_name'):
        # Clear the flag
        context.user_data['awaiting_cert_name'] = False
        
        # Get the certificate name from the message
        cert_name = update.message.text.strip()
        
        # Basic validation
        if not cert_name:
            await update.message.reply_text(
                'Certificate name cannot be empty. Please try again.',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Certificate List", callback_data="cert_list")
                ]])
            )
            return
        
        # Generate the certificate
        from openvpn_bot.utils.cert_manager import generate_certificate
        success, message = generate_certificate(cert_name)
        
        if success:
            await update.message.reply_text(
                f'✅ Certificate generated successfully: {cert_name}',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Certificate List", callback_data="cert_list")
                ]])
            )
        else:
            await update.message.reply_text(
                f'❌ Error generating certificate: {message}',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Certificate List", callback_data="cert_list")
                ]])
            )
    else:
        # Handle any other unexpected messages
        await update.message.reply_text(
            'Use the buttons below or tap Start to open the menu.',
            reply_markup=main_menu_keyboard()
        )


async def traffic_check_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic job to check traffic thresholds and send notifications."""
    logger.debug("Running periodic traffic check...")
    result = await check_and_notify(context)
    if result['errors']:
        logger.warning(f"Traffic check completed with errors: {result['errors']}")


def main() -> None:
    """Start the bot."""
    # Configure logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(Config.TELEGRAM_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Service management
    application.add_handler(CommandHandler("status", service_status))
    application.add_handler(CommandHandler("start_vpn", service_start))
    application.add_handler(CommandHandler("stop_vpn", service_stop))
    application.add_handler(CommandHandler("restart_vpn", service_restart))
    
    # Client management
    application.add_handler(CommandHandler("clients", clients_list))
    application.add_handler(CommandHandler("disconnect", client_disconnect))
    
    # Traffic monitoring
    application.add_handler(CommandHandler("traffic", traffic_stats))
    application.add_handler(CommandHandler("user_traffic", user_traffic))
    application.add_handler(CommandHandler("throttle", traffic_thresholds))
    application.add_handler(CommandHandler("traffic_check", traffic_check))
    application.add_handler(CommandHandler("reset_traffic_alerts", reset_traffic_notifications))
    
    # Certificate management
    application.add_handler(CommandHandler("cert_list", cert_list))
    application.add_handler(CommandHandler("cert_generate", cert_generate))
    application.add_handler(CommandHandler("cert_revoke", cert_revoke))
    application.add_handler(CommandHandler("cert_renew", cert_renew))
    application.add_handler(CommandHandler("cert_ban", cert_ban))
    application.add_handler(CommandHandler("cert_unban", cert_unban))
    
    # Button callbacks
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Handle text messages (for certificate generation input and fallback)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Setup periodic traffic check job (if traffic monitor is available)
    if Config.TRAFFIC_MONITOR_AVAILABLE:
        job_queue = application.job_queue
        # Run traffic check every TRAFFIC_CHECK_INTERVAL seconds
        job_queue.run_repeating(
            traffic_check_job,
            interval=Config.TRAFFIC_CHECK_INTERVAL,
            first=60  # First check after 60 seconds
        )
        logger.info(
            f"Traffic threshold monitoring enabled. "
            f"Check interval: {Config.TRAFFIC_CHECK_INTERVAL} seconds"
        )
    else:
        logger.info("Traffic threshold monitoring disabled (traffic monitor not available)")

    # Start the Bot
    logger.info("Starting OpenVPN Telegram Bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
