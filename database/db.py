from datetime import datetime, timedelta
import sqlite3
from config import DB_NAME


def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    # Enable SQLite foreign key constraint enforcement
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table (Includes Referral Tracking)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            referred_by INTEGER,
            points INTEGER DEFAULT 0,
            referrals_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referred_by) REFERENCES users (user_id) ON DELETE SET NULL
        )
    """
    )

    # 2. Products Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            price REAL NOT NULL,
            size TEXT NOT NULL,
            stock INTEGER DEFAULT 0,
            photo_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # 3. Cart Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            selected_size TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
    """
    )

    # 4. Orders Master Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT,
            phone_number TEXT NOT NULL,
            total_price REAL NOT NULL,
            delivery_fee REAL DEFAULT 200.0,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # 5. Order Details Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            selected_size TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    """
    )

    conn.commit()
    conn.close()


# ----- User & Referral Functions -----


async def register_user(user_id: int, username: str, referred_by: int = None) -> bool:
    """Registers a user if they do not exist. Returns True if a new user was created."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    existing_user = cursor.fetchone()

    if existing_user:
        conn.close()
        return False  # User already exists

    # Insert new user record
    cursor.execute(
        "INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
        (user_id, username, referred_by),
    )
    conn.commit()
    conn.close()
    return True  # New user successfully registered


async def add_referral_points(referrer_id: int, points: int = 1):
    """Increments referral points and count for the referrer."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE users 
        SET points = points + ?, referrals_count = referrals_count + 1 
        WHERE user_id = ?
        """,
        (points, referrer_id),
    )
    conn.commit()
    conn.close()


async def get_user_stats(user_id: int) -> dict:
    """Retrieves referral stats and points for a given user."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT points, referrals_count FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {"points": row["points"], "referrals_count": row["referrals_count"]}
    return {"points": 0, "referrals_count": 0}


# ----- Product Functions -----


def add_product(name, price, size, stock, photo_id_list, category=None):
    conn = get_db()
    cursor = conn.cursor()

    photos_str = (
        ",".join(photo_id_list)
        if isinstance(photo_id_list, list)
        else photo_id_list
    )

    cursor.execute(
        "INSERT INTO products (name, category, price, size, stock, photo_id) VALUES (?, ?, ?, ?, ?, ?)",
        (name, category, price, size, stock, photos_str),
    )
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id


def get_all_products():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE stock > 0 ORDER BY id DESC")
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return products


def get_product_by_id(product_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_product_by_id(product_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart WHERE product_id = ?", (product_id,))
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def update_product_stock(product_id, new_stock):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id)
    )
    conn.commit()
    conn.close()


# ----- Cart & Stock Reservation Functions -----


def cleanup_expired_carts(existing_cursor=None):
    """If a cursor is supplied, reuses connection; otherwise manages its own."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query = "DELETE FROM cart WHERE expires_at IS NOT NULL AND expires_at < ?"

    if existing_cursor:
        existing_cursor.execute(query, (now_str,))
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(query, (now_str,))
        conn.commit()
        conn.close()


def add_to_cart(user_id, product_id, size, quantity=1, timeout_minutes=30):
    conn = get_db()
    cursor = conn.cursor()

    cleanup_expired_carts(existing_cursor=cursor)

    # 1. Verify Product Stock
    cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()

    if not product or product["stock"] <= 0:
        conn.close()
        return False, "Product out of stock."

    # 2. Check current cart quantity for user
    cursor.execute(
        "SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ? AND selected_size = ?",
        (user_id, product_id, str(size)),
    )
    item = cursor.fetchone()

    current_in_cart = item["quantity"] if item else 0
    if (current_in_cart + quantity) > product["stock"]:
        conn.close()
        return (
            False,
            f"Not enough stock available. Remaining stock: {product['stock']}",
        )

    expires_at = (
        datetime.now() + timedelta(minutes=timeout_minutes)
    ).strftime("%Y-%m-%d %H:%M:%S")

    if item:
        cursor.execute(
            "UPDATE cart SET quantity = quantity + ?, expires_at = ? WHERE id = ?",
            (quantity, expires_at, item["id"]),
        )
    else:
        cursor.execute(
            "INSERT INTO cart (user_id, product_id, selected_size, quantity, expires_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, product_id, str(size), quantity, expires_at),
        )

    conn.commit()
    conn.close()
    return True, "Item added to cart successfully."


def decrease_cart_quantity(user_id, product_id, size, timeout_minutes=30):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, quantity FROM cart 
        WHERE user_id = ? AND product_id = ? AND selected_size = ?
    """,
        (user_id, product_id, str(size)),
    )
    item = cursor.fetchone()

    if item:
        expires_at = (
            datetime.now() + timedelta(minutes=timeout_minutes)
        ).strftime("%Y-%m-%d %H:%M:%S")

        if item["quantity"] > 1:
            cursor.execute(
                "UPDATE cart SET quantity = quantity - 1, expires_at = ? WHERE id = ?",
                (expires_at, item["id"]),
            )
        else:
            cursor.execute("DELETE FROM cart WHERE id = ?", (item["id"],))
        conn.commit()
    conn.close()


def get_user_cart(user_id, existing_cursor=None):
    """Can run independently or receive an active cursor to stay inside a single transaction."""
    if existing_cursor:
        cleanup_expired_carts(existing_cursor=existing_cursor)
        existing_cursor.execute(
            """
            SELECT c.id as cart_id, c.product_id, c.selected_size, c.quantity, c.expires_at, p.name, p.price, p.stock 
            FROM cart c 
            JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = ?
        """,
            (user_id,),
        )
        return [dict(row) for row in existing_cursor.fetchall()]

    conn = get_db()
    cursor = conn.cursor()
    cleanup_expired_carts(existing_cursor=cursor)
    cursor.execute(
        """
        SELECT c.id as cart_id, c.product_id, c.selected_size, c.quantity, c.expires_at, p.name, p.price, p.stock 
        FROM cart c 
        JOIN products p ON c.product_id = p.id 
        WHERE c.user_id = ?
    """,
        (user_id,),
    )
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items


def clear_user_cart(user_id, existing_cursor=None):
    if existing_cursor:
        existing_cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()


# ----- Order & Tracking Functions -----


def create_multi_item_order(user_id, user_name, phone_number):
    """Atomic Order creation maintaining inventory safety."""
    conn = get_db()
    cursor = conn.cursor()

    try:
        cart_items = get_user_cart(user_id, existing_cursor=cursor)
        if not cart_items:
            conn.close()
            return None, "Cart is empty."

        # 1. Final stock verification before processing
        subtotal = 0.0
        for item in cart_items:
            cursor.execute(
                "SELECT stock FROM products WHERE id = ?",
                (item["product_id"],),
            )
            p = cursor.fetchone()
            if not p or p["stock"] < item["quantity"]:
                conn.close()
                return (
                    None,
                    f"Insufficient stock for item '{item['name']}'.",
                )
            subtotal += item["price"] * item["quantity"]

        # 2. Delivery Fee Logic (Free above 2000 ETB)
        delivery_fee = 0.0 if subtotal >= 2000.0 else 200.0
        grand_total = subtotal + delivery_fee

        # 3. Create Order Record
        cursor.execute(
            "INSERT INTO orders (user_id, user_name, phone_number, total_price, delivery_fee) VALUES (?, ?, ?, ?, ?)",
            (user_id, user_name, phone_number, grand_total, delivery_fee),
        )
        order_id = cursor.lastrowid

        # 4. Insert Order Items
        for item in cart_items:
            cursor.execute(
                """INSERT INTO order_items (order_id, product_id, product_name, selected_size, quantity, unit_price)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    order_id,
                    item["product_id"],
                    item["name"],
                    str(item["selected_size"]),
                    item["quantity"],
                    item["price"],
                ),
            )

        clear_user_cart(user_id, existing_cursor=cursor)
        conn.commit()
        conn.close()
        return (order_id, grand_total, cart_items, delivery_fee), "Success"

    except Exception as e:
        conn.rollback()
        conn.close()
        return None, f"Error: {str(e)}"


def get_user_orders(user_id, limit=5):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return orders


def get_order_details(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return None, []

    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return dict(order), items


def update_order_status(order_id, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET status = ? WHERE id = ?", (status, order_id)
    )

    if status == "APPROVED":
        cursor.execute(
            "SELECT product_id, quantity FROM order_items WHERE order_id = ?",
            (order_id,),
        )
        items = cursor.fetchall()
        for item in items:
            cursor.execute(
                "UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?",
                (item["quantity"], item["product_id"]),
            )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialization completed successfully!")