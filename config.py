import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin IDs
raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()]

# Admin Channel / Group ID
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID", "")
CHANNEL_ID = os.getenv("ADMIN_GROUP_ID", "")

# Database Name
DB_NAME = os.getenv("DB_NAME", "store.db")
