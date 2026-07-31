import sqlite3
import logging

DB_PATH = "shoe_store.db"

logger = logging.getLogger(__name__)


def init_users_db():
    """Initializes the users table if it does not exist"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                referred_by INTEGER,
                points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error initializing users database: {e}")


def get_user(telegram_id: int):
    """Fetches user details from the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT telegram_id, referred_by, points FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Error fetching user {telegram_id}: {e}")
        return None


def add_user(telegram_id: int, referred_by: int = None):
    """Registers a new user in the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (telegram_id, referred_by) VALUES (?, ?)",
            (telegram_id, referred_by),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error adding user {telegram_id}: {e}")


def add_referral_points(telegram_id: int, points: int = 10):
    """Increases reward points for the referrer"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET points = points + ? WHERE telegram_id = ?",
            (points, telegram_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error adding points to {telegram_id}: {e}")
