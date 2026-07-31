import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Read credentials
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Parse ADMIN_IDS into a list of integers
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

# Parse CHANNEL_ID to integer if present
channel_id_env = os.getenv("CHANNEL_ID", "")
CHANNEL_ID = int(channel_id_env.strip()) if channel_id_env.strip() else None
# የDatabase ፋይል ስም
DB_NAME = "store.db"
