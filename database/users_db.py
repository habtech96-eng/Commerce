import sqlite3
import logging
from config import DB_NAME  # Ensure this imports your actual DB name (e.g., 'shoe_store.db')

DB_PATH = DB_NAME

logger = logging.getLogger(__name__)

def init_users_db():
    """Users table is now initialized in db.py to avoid conflicts. 
    Keeping this function empty so main.py doesn't crash."""
    pass

def get_user(user_id: int):
    """Fetches full user details from the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, username, referred_by, points, referrals_count 
            FROM users WHERE user_id = ?
            """,
            (user_id,),
        )
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return None

def add_user(user_id: int, username: str = None, referred_by: int = None):
    """Registers a new user and updates referrer's invite count"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
            (user_id, username, referred_by),
        )
        
        # Increment referrer's referrals_count if invited by someone
        if referred_by:
            cursor.execute(
                "UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?",
                (referred_by,),
            )
            
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")

def add_referral_points(user_id: int, points: int = 10):
    """Increases reward points for a user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET points = points + ? WHERE user_id = ?",
            (points, user_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error adding points to {user_id}: {e}")

def deduct_points(user_id: int, points: int) -> bool:
    """Deducts points for discounts/coupons if the user has enough balance"""
    user = get_user(user_id)
    if not user or user[3] < points:  # user[3] is the points column in the updated schema
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET points = points - ? WHERE user_id = ? AND points >= ?",
            (points, user_id, points),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error deducting points from {user_id}: {e}")
        return False

def get_top_referrers(limit: int = 10):
    """Fetches top users for Leaderboard"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT username, referrals_count, points 
            FROM users 
            ORDER BY referrals_count DESC, points DESC 
            LIMIT ?
            """,
            (limit,),
        )
        top_users = cursor.fetchall()
        conn.close()
        return top_users
    except Exception as e:
        logger.error(f"Error fetching top referrers: {e}")
        return []

def get_all_user_ids():
    """Fetches all registered Telegram user IDs for admin broadcasts."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Error fetching user IDs: {e}")
        return []
