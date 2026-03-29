import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from openvpn_bot.config import Config
from openvpn_bot.utils import validate_username

logger = logging.getLogger(__name__)


def get_db_connection():
    """Create a database connection."""
    return sqlite3.connect(Config.OPENVPN_DB_PATH)


def get_current_month_traffic() -> int:
    """Get total traffic for the current month in bytes."""
    if not Config.TRAFFIC_MONITOR_AVAILABLE:
        return 0
    
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_month = datetime.now().strftime('%Y-%m')
            c.execute('''
                SELECT SUM(bytes_received + bytes_sent) 
                FROM user_traffic_monthly 
                WHERE year_month = ?
            ''', (current_month,))
            result = c.fetchone()[0]
            return result if result is not None else 0
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error(f"Database error in get_current_month_traffic: {e}")
        return 0


def get_user_traffic(username: str) -> Dict[str, int]:
    """Get traffic for a specific user for the current month."""
    # Check if traffic monitor is available
    if not Config.TRAFFIC_MONITOR_AVAILABLE:
        return {'received': 0, 'sent': 0, 'total': 0, 'available': False}
    
    # Validate username using common validator
    if not validate_username(username):
        return {'received': 0, 'sent': 0, 'total': 0, 'available': True, 'error': 'Invalid username'}
    
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_month = datetime.now().strftime('%Y-%m')
            c.execute('''
                SELECT bytes_received, bytes_sent 
                FROM user_traffic_monthly 
                WHERE common_name = ? AND year_month = ?
            ''', (username, current_month))
            result = c.fetchone()
            if result:
                return {'received': result[0], 'sent': result[1], 'total': result[0] + result[1], 'available': True}
            return {'received': 0, 'sent': 0, 'total': 0, 'available': True}
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error(f"Database error in get_user_traffic: {e}")
        return {'received': 0, 'sent': 0, 'total': 0, 'available': True, 'error': str(e)}


def get_top_users(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users by traffic for the current month."""
    if not Config.TRAFFIC_MONITOR_AVAILABLE:
        return []
    
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_month = datetime.now().strftime('%Y-%m')
            c.execute('''
                SELECT common_name, (bytes_received + bytes_sent) as total
                FROM user_traffic_monthly
                WHERE year_month = ?
                ORDER BY total DESC
                LIMIT ?
            ''', (current_month, limit))
            rows = c.fetchall()
            return [{'user': row[0], 'total': row[1]} for row in rows]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error(f"Database error in get_top_users: {e}")
        return []


def check_traffic_thresholds() -> Dict[str, Any]:
    """Check if current month traffic has crossed any of the configured thresholds."""
    result = {
        'total_gb': 0,
        'crossed_thresholds': [],
        'all_thresholds': Config.TRAFFIC_THRESHOLDS,
        'available': Config.TRAFFIC_MONITOR_AVAILABLE,
        'error': None
    }
    
    if not Config.TRAFFIC_MONITOR_AVAILABLE:
        return result
    
    total_bytes = get_current_month_traffic()
    total_gb = total_bytes / (1024 ** 3)  # Convert to GB
    
    crossed = []
    for threshold in Config.TRAFFIC_THRESHOLDS:
        if total_gb >= threshold:
            crossed.append(threshold)
    
    result['total_gb'] = total_gb
    result['crossed_thresholds'] = crossed
    
    return result


def get_month_traffic(year_month: str) -> int:
    """Get total traffic for a specific month (format: YYYY-MM) in bytes."""
    if not Config.TRAFFIC_MONITOR_AVAILABLE:
        return 0
    
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT SUM(bytes_received + bytes_sent) 
                FROM user_traffic_monthly 
                WHERE year_month = ?
            ''', (year_month,))
            result = c.fetchone()[0]
            return result if result is not None else 0
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error(f"Database error in get_month_traffic: {e}")
        return 0


def get_all_users_traffic(year_month: str) -> List[Dict[str, Any]]:
    """Get all users with their traffic for a specific month."""
    if not Config.TRAFFIC_MONITOR_AVAILABLE:
        return []
    
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT common_name, bytes_received, bytes_sent
                FROM user_traffic_monthly
                WHERE year_month = ?
                ORDER BY (bytes_received + bytes_sent) DESC
            ''', (year_month,))
            rows = c.fetchall()
            return [
                {
                    'user': row[0],
                    'received': row[1],
                    'sent': row[2],
                    'total': row[1] + row[2]
                }
                for row in rows
            ]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error(f"Database error in get_all_users_traffic: {e}")
        return []


def get_last_month_str() -> str:
    """Return last month as YYYY-MM string."""
    from datetime import timedelta
    first_of_month = datetime.now().replace(day=1)
    last_month = first_of_month - timedelta(days=1)
    return last_month.strftime('%Y-%m')
