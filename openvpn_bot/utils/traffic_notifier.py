"""
Traffic notification module for OpenVPN Telegram Bot.

This module provides automatic notifications when traffic thresholds are exceeded.
Notifications are sent to all configured administrators.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from openvpn_bot.config import Config
from openvpn_bot.utils.traffic_monitor import check_traffic_thresholds

logger = logging.getLogger(__name__)

# Track which thresholds have been notified to avoid spam
# Key: threshold value, Value: set of notified admin IDs
_notified_thresholds: Dict[int, Set[int]] = {}


def reset_notifications():
    """Reset all notification tracking. Useful for testing."""
    global _notified_thresholds
    _notified_thresholds.clear()


def format_notification_message(data: Dict) -> str:
    """
    Format a traffic threshold notification message.
    
    Args:
        data: Dictionary with threshold data from check_traffic_thresholds()
        
    Returns:
        Formatted message string
    """
    month_name = datetime.now().strftime('%B %Y')
    
    message_lines = [
        "🚨 **Traffic threshold exceeded!**\n",
        f"📅 Period: {month_name}",
        f"📊 Current usage: {data['total_gb']:.2f} GB\n",
        "**Threshold status:**"
    ]
    
    for threshold in data['all_thresholds']:
        if threshold in data['crossed_thresholds']:
            diff = data['total_gb'] - threshold
            message_lines.append(f"• {threshold} GB: ⚠️ Exceeded (+{diff:.2f} GB)")
        else:
            message_lines.append(f"• {threshold} GB: ✅ Not exceeded")
    
    #message_lines.append("\nView details: /throttle")
    
    return "\n".join(message_lines)


def should_notify(threshold: int, admin_id: int) -> bool:
    """
    Check if we should send notification for a threshold to a specific admin.
    
    This implements a "notify once" mechanism - once a threshold is crossed,
    we notify the admin once. We reset when the threshold is no longer crossed.
    
    Args:
        threshold: The threshold value
        admin_id: The admin user ID
        
    Returns:
        True if notification should be sent
    """
    if threshold not in _notified_thresholds:
        return True
    return admin_id not in _notified_thresholds[threshold]


def mark_notified(threshold: int, admin_id: int):
    """
    Mark a threshold as notified for a specific admin.
    
    Args:
        threshold: The threshold value
        admin_id: The admin user ID
    """
    if threshold not in _notified_thresholds:
        _notified_thresholds[threshold] = set()
    _notified_thresholds[threshold].add(admin_id)


def cleanup_stale_notifications(crossed_thresholds: List[int]):
    """
    Remove notifications for thresholds that are no longer crossed.
    
    Args:
        crossed_thresholds: List of currently crossed thresholds
    """
    thresholds_to_remove = []
    for threshold in _notified_thresholds:
        if threshold not in crossed_thresholds:
            thresholds_to_remove.append(threshold)
    
    for threshold in thresholds_to_remove:
        del _notified_thresholds[threshold]
        logger.debug(f"Cleaned up notifications for threshold {threshold} GB")


async def check_and_notify(context) -> Dict:
    """
    Check traffic thresholds and send notifications to admins if exceeded.
    
    This function is designed to be called periodically by JobQueue.
    
    Args:
        context: The telegram.ext.ContextTypes.DEFAULT_TYPE context
        
    Returns:
        Dictionary with check results
    """
    result = {
        'checked': False,
        'notified': [],
        'errors': []
    }
    
    # Check if traffic monitor is available
    if not Config.TRAFFIC_MONITOR_AVAILABLE:
        result['errors'].append("Traffic monitor not available")
        return result
    
    try:
        # Get threshold data
        threshold_data = check_traffic_thresholds()
        result['checked'] = True
        result['total_gb'] = threshold_data['total_gb']
        result['crossed_thresholds'] = threshold_data['crossed_thresholds']
        
        # Cleanup stale notifications
        cleanup_stale_notifications(threshold_data['crossed_thresholds'])
        
        # If no thresholds are crossed, we're done
        if not threshold_data['crossed_thresholds']:
            logger.debug(
                f"Traffic check: {threshold_data['total_gb']:.2f} GB - "
                f"No thresholds crossed"
            )
            return result
        
        # Format notification message
        message = format_notification_message(threshold_data)
        
        # Send notification to each admin who hasn't been notified
        for admin_id in Config.ADMIN_IDS:
            for threshold in threshold_data['crossed_thresholds']:
                if should_notify(threshold, admin_id):
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                        mark_notified(threshold, admin_id)
                        result['notified'].append({
                            'admin_id': admin_id,
                            'threshold': threshold
                        })
                        logger.info(
                            f"Sent threshold notification to admin {admin_id} "
                            f"for threshold {threshold} GB"
                        )
                    except Exception as e:
                        error_msg = f"Failed to notify admin {admin_id}: {e}"
                        logger.error(error_msg)
                        result['errors'].append(error_msg)
        
        logger.info(
            f"Traffic check completed: {threshold_data['total_gb']:.2f} GB, "
            f"crossed thresholds: {threshold_data['crossed_thresholds']}, "
            f"notified admins: {len(result['notified'])}"
        )
        
    except Exception as e:
        error_msg = f"Error during traffic check: {e}"
        logger.error(error_msg)
        result['errors'].append(error_msg)
    
    return result
