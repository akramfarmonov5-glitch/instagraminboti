"""
Instagram DM Bot Configuration
Environment variables va global settings
"""
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime

# Load environment variables
load_dotenv()

# ============== API CREDENTIALS ==============
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

# ============== PATHS ==============
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SESSION_FILE = DATA_DIR / "session.json"
DATABASE_FILE = DATA_DIR / "leads.db"
DATABASE_URL = os.getenv("DATABASE_URL", "") # Neon PostgreSQL URL

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# ============== RATE LIMITING (Gradual Warmup) ==============
# Day ranges and their DM limits
DM_LIMITS = {
    (1, 3): 8,      # Days 1-3: max 8 DMs
    (4, 7): 15,     # Days 4-7: max 15 DMs
    (8, 14): 25,    # Days 8-14: max 25 DMs
    (15, 999): 40,  # 15+ days: max 40 DMs
}

# Inbox check interval (seconds) - random between these values
INBOX_CHECK_MIN = 420  # 7 minutes
INBOX_CHECK_MAX = 720  # 12 minutes

# ============== HUMAN SIMULATION ==============
# Typing delay formula: len(message) * TYPING_SPEED + random(DELAY_MIN, DELAY_MAX)
TYPING_SPEED = 0.4  # seconds per character
DELAY_MIN = 5       # minimum additional delay
DELAY_MAX = 15      # maximum additional delay

# ============== SAFETY SETTINGS ==============
# Kill-switch: pause bot for 24h if these conditions met
CONSECUTIVE_REJECTIONS_LIMIT = 2  # 2 "kerak emas" in a row
KILL_SWITCH_DURATION = 24 * 60 * 60  # 24 hours in seconds

# ============== CONFIDENCE SCORING ==============
SCORE_ASKED_QUESTION = 1
SCORE_MENTIONED_PROBLEM = 2
SCORE_SHORT_COLD_REPLY = -3
SCORE_REJECTION = -5
SCORE_THRESHOLD = 0  # Exit if score drops below this

# ============== TIME OF DAY ==============
def get_time_of_day() -> str:
    """Returns current time period: morning, afternoon, or evening"""
    hour = datetime.now().hour
    if 8 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    else:
        return "evening"

# ============== VALIDATION ==============
def validate_config() -> bool:
    """Check if all required credentials are set"""
    missing = []
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not INSTAGRAM_USERNAME:
        missing.append("INSTAGRAM_USERNAME")
    if not INSTAGRAM_PASSWORD:
        missing.append("INSTAGRAM_PASSWORD")
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("Please create a .env file with these values.")
        return False
    return True
