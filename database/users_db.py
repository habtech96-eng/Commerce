import sqlite3
import logging

DB_PATH = "shoe_store.db"

logger = logging.getLogger(__name__)


def init_users_db():
    """Initializes the users table with referral and point tracking columns"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                referred_by INTEGER,
                points INTEGER DEFAULT 0,
                total_referrals INTEGER DEFAULT 0,
                successful_purchases INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error initializing users database: {e}")


def get_user(telegram_id: int):
    """Fetches full user details from the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT telegram_id, referred_by, points, total_referrals, successful_purchases 
            FROM users WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Error fetching user {telegram_id}: {e}")
        return None


def add_user(telegram_id: int, referred_by: int = None):
    """Registers a new user and updates referrer's invite count"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (telegram_id, referred_by) VALUES (?, ?)",
            (telegram_id, referred_by),
        )
        
        # Increment referrer's total_referrals count if invited by someone
        if referred_by:
            cursor.execute(
                "UPDATE users SET total_referrals = total_referrals + 1 WHERE telegram_id = ?",
                (referred_by,),
            )
            
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error adding user {telegram_id}: {e}")


def add_referral_points(telegram_id: int, points: int = 10):
    """Increases reward points for a user"""
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


def deduct_points(telegram_id: int, points: int) -> bool:
    """Deducts points for discounts/coupons if the user has enough balance"""
    user = get_user(telegram_id)
    if not user or user[2] < points:  # user[2] is points column
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET points = points - ? WHERE telegram_id = ? AND points >= ?",
            (points, telegram_id, points),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error deducting points from {telegram_id}: {e}")
        return False


def record_successful_purchase(buyer_id: int, reward_referrer_points: int = 20):
    """Increments buyer's completed orders and rewards referrer on first purchase"""
    user = get_user(buyer_id)
    if not user:
        return

    referrer_id = user[1]
    purchases_count = user[4]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Update buyer's purchase count
        cursor.execute(
            "UPDATE users SET successful_purchases = successful_purchases + 1 WHERE telegram_id = ?",
            (buyer_id,),
        )
        
        # Reward referrer if it's the buyer's first successful purchase
        if purchases_count == 0 and referrer_id:
            cursor.execute(
                "UPDATE users SET points = points + ? WHERE telegram_id = ?",
                (reward_referrer_points, referrer_id),
            )
            
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error recording purchase for {buyer_id}: {e}")


def get_top_referrers(limit: int = 10):
    """Fetches top users for Leaderboard"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT telegram_id, total_referrals, points 
            FROM users 
            ORDER BY total_referrals DESC, points DESC 
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

def get_top_referrers(limit=10):
    """Fetches top users sorted by their referral count"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT first_name, referral_count, points FROM users ORDER BY referral_count DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        return []

def get_all_user_ids():
    """Fetches all registered Telegram user IDs for admin broadcasts."""
    import sqlite3
    
    # Replace 'users.db' with your actual database path/connection function if different
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT telegram_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    # Returns a flat list of user IDs: [12345678, 87654321, ...]
    return [row[0] for row in rows]
