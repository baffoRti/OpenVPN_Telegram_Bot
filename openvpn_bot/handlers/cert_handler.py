from telegram import Update
from telegram.ext import ContextTypes
from openvpn_bot.utils.cert_manager import (
    generate_certificate, revoke_certificate, renew_certificate, 
    list_certificates, ban_certificate, unban_certificate
)
from openvpn_bot.config import Config

async def cert_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cert_list command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    success, message = list_certificates()
    if success:
        await update.message.reply_text(f'📋 Certificates:\n\n{message}')
    else:
        # Extract simple error message
        error_msg = message.split('\n')[-1] if '\n' in message else message
        await update.message.reply_text(f'❌ Error: {error_msg}')

async def cert_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cert_generate command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    if not context.args:
        await update.message.reply_text('Please specify a common name for the certificate.\nUsage: /cert_generate <common_name>')
        return
    
    common_name = context.args[0]
    success, message = generate_certificate(common_name)

    if success:
        await update.message.reply_text(f'✅ Certificate created: {common_name}')
    else:
        await update.message.reply_text(f'❌ Failed to create certificate: {message}')

async def cert_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cert_revoke command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    if not context.args:
        await update.message.reply_text('Please specify a common name for the certificate to revoke.\nUsage: /cert_revoke <common_name>')
        return
    
    common_name = context.args[0]
    success, message = revoke_certificate(common_name)

    if success:
        await update.message.reply_text(f'✅ Certificate revoked: {common_name}')
    else:
        await update.message.reply_text(f'❌ Failed to revoke certificate: {message}')

async def cert_renew(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cert_renew command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    if not context.args:
        await update.message.reply_text('Please specify a common name for the certificate to renew.\nUsage: /cert_renew <common_name>')
        return
    
    common_name = context.args[0]
    success, message = renew_certificate(common_name)

    if success:
        await update.message.reply_text(f'✅ Certificate renewed: {common_name}')
    else:
        await update.message.reply_text(f'❌ Failed to renew certificate: {message}')

async def cert_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cert_ban command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    if not context.args:
        await update.message.reply_text('Please specify a common name for the certificate to ban.\nUsage: /cert_ban <common_name>')
        return
    
    common_name = context.args[0]
    success, message = ban_certificate(common_name)

    if success:
        await update.message.reply_text(f'✅ Certificate banned: {common_name}')
    else:
        await update.message.reply_text(f'❌ Failed to ban certificate: {message}')

async def cert_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cert_unban command."""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text('You are not authorized to use this bot.')
        return
    
    if not context.args:
        await update.message.reply_text('Please specify a common name for the certificate to unban.\nUsage: /cert_unban <common_name>')
        return
    
    common_name = context.args[0]
    success, message = unban_certificate(common_name)

    if success:
        await update.message.reply_text(f'✅ Certificate unbanned: {common_name}')
    else:
        await update.message.reply_text(f'❌ Failed to unban certificate: {message}')
