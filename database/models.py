"""
Database Models and Schema
SQLite database for leads, conversations, and messages
"""
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
import json

from config import DATABASE_FILE, DATABASE_URL


def get_connection():
    """Get database connection (PostgreSQL if DATABASE_URL set, otherwise SQLite)"""
    if DATABASE_URL:
        # PostgreSQL (Neon)
        conn = psycopg2.connect(DATABASE_URL)
        return conn, "%s" # Placeholder for PG
    else:
        # Local SQLite
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        return conn, "?"  # Placeholder for SQLite


def get_cursor(conn):
    """Get a cursor that returns results as dictionaries"""
    if isinstance(conn, sqlite3.Connection):
        return conn.cursor()
    else:
        # PostgreSQL
        return conn.cursor(cursor_factory=RealDictCursor)


def init_database():
    """Initialize database tables"""
    conn, _ = get_connection()
    cursor = get_cursor(conn)
    
    # Check if we are using PostgreSQL
    is_pg = not isinstance(conn, sqlite3.Connection)
    id_type = "SERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    # Leads table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS leads (
            id {id_type},
            username TEXT UNIQUE NOT NULL,
            bio TEXT,
            last_post_topic TEXT,
            niche TEXT,
            status TEXT DEFAULT 'new',
            confidence_score INTEGER DEFAULT 0,
            consecutive_rejections INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Conversations table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS conversations (
            id {id_type},
            lead_id INTEGER NOT NULL,
            state TEXT DEFAULT 'new',
            message_count INTEGER DEFAULT 0,
            last_message_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
    """)
    
    # Messages table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS messages (
            id {id_type},
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)
    
    # Bot state table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS bot_state (
            id INTEGER PRIMARY KEY,
            paused_until TIMESTAMP,
            total_dms_today INTEGER DEFAULT 0,
            last_dm_date DATE,
            account_created_date DATE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Initialize bot state if not exists
    if is_pg:
        cursor.execute("INSERT INTO bot_state (id, total_dms_today, last_dm_date) VALUES (1, 0, CURRENT_DATE) ON CONFLICT (id) DO NOTHING")
    else:
        cursor.execute("INSERT OR IGNORE INTO bot_state (id, total_dms_today, last_dm_date) VALUES (1, 0, date('now'))")
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")


# ============== LEAD OPERATIONS ==============

def add_lead(username: str, bio: str = "", last_post_topic: str = "", niche: str = "") -> int:
    """Add a new lead to database, returns lead_id"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    is_pg = not isinstance(conn, sqlite3.Connection)
    
    try:
        if is_pg:
            cursor.execute(f"""
                INSERT INTO leads (username, bio, last_post_topic, niche)
                VALUES ({p}, {p}, {p}, {p})
                ON CONFLICT (username) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (username, bio, last_post_topic, niche))
            row = cursor.fetchone()
            lead_id = row['id']
        else:
            cursor.execute(f"""
                INSERT OR IGNORE INTO leads (username, bio, last_post_topic, niche)
                VALUES ({p}, {p}, {p}, {p})
            """, (username, bio, last_post_topic, niche))
            if cursor.rowcount == 0:
                # If insert ignored, lead already exists, fetch its ID
                cursor.execute(f"SELECT id FROM leads WHERE username = {p}", (username,))
                row = cursor.fetchone()
                lead_id = row['id']
            else:
                lead_id = cursor.lastrowid
        
        # Create or Get conversation for this lead
        if is_pg:
            cursor.execute(f"""
                INSERT INTO conversations (lead_id, state)
                VALUES ({p}, 'new')
                ON CONFLICT (lead_id) DO NOTHING
            """, (lead_id,))
        else:
            cursor.execute(f"""
                INSERT OR IGNORE INTO conversations (lead_id, state)
                VALUES ({p}, 'new')
            """, (lead_id,))
            
        conn.commit()
        return lead_id
    finally:
        conn.close()


def get_lead_by_username(username: str) -> Optional[dict]:
    """Get lead by username"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"SELECT * FROM leads WHERE username = {p}", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_leads_by_status(status: str) -> list:
    """Get all leads with given status"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"SELECT * FROM leads WHERE status = {p}", (status,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_lead_status(username: str, status: str):
    """Update lead status"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        UPDATE leads 
        SET status = {p}, updated_at = CURRENT_TIMESTAMP
        WHERE username = {p}
    """, (status, username))
    conn.commit()
    conn.close()


def update_lead_score(username: str, score_delta: int):
    """Update lead confidence score"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        UPDATE leads 
        SET confidence_score = confidence_score + {p}, updated_at = CURRENT_TIMESTAMP
        WHERE username = {p}
    """, (score_delta, username))
    conn.commit()
    conn.close()


def increment_rejections(username: str) -> int:
    """Increment consecutive rejections, returns new count"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        UPDATE leads 
        SET consecutive_rejections = consecutive_rejections + 1, updated_at = CURRENT_TIMESTAMP
        WHERE username = {p}
    """, (username,))
    cursor.execute(f"SELECT consecutive_rejections FROM leads WHERE username = {p}", (username,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return row['consecutive_rejections'] if row else 0


def reset_rejections(username: str):
    """Reset consecutive rejections to 0"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        UPDATE leads 
        SET consecutive_rejections = 0, updated_at = CURRENT_TIMESTAMP
        WHERE username = {p}
    """, (username,))
    conn.commit()
    conn.close()


# ============== CONVERSATION OPERATIONS ==============

def get_conversation(lead_id: int) -> Optional[dict]:
    """Get conversation for a lead"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"SELECT * FROM conversations WHERE lead_id = {p}", (lead_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_conversation_state(lead_id: int, state: str):
    """Update conversation state"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        UPDATE conversations 
        SET state = {p}, last_message_at = CURRENT_TIMESTAMP
        WHERE lead_id = {p}
    """, (state, lead_id))
    conn.commit()
    conn.close()


def increment_message_count(lead_id: int):
    """Increment message count for conversation"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        UPDATE conversations 
        SET message_count = message_count + 1, last_message_at = CURRENT_TIMESTAMP
        WHERE lead_id = {p}
    """, (lead_id,))
    conn.commit()
    conn.close()


# ============== MESSAGE OPERATIONS ==============

def add_message(conversation_id: int, role: str, content: str):
    """Add a message to conversation history"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        INSERT INTO messages (conversation_id, role, content)
        VALUES ({p}, {p}, {p})
    """, (conversation_id, role, content))
    conn.commit()
    conn.close()


def get_conversation_history(conversation_id: int) -> list:
    """Get all messages in a conversation"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        SELECT role, content, created_at 
        FROM messages 
        WHERE conversation_id = {p}
        ORDER BY created_at ASC
    """, (conversation_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============== BOT STATE OPERATIONS ==============

def is_bot_paused() -> bool:
    """Check if bot is in pause state (kill-switch active)"""
    conn, _ = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("SELECT paused_until FROM bot_state WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    if row and row['paused_until']:
        try:
            # Handle both string (SQLite) and datetime (PG)
            if isinstance(row['paused_until'], str):
                paused_until = datetime.fromisoformat(row['paused_until'])
            else:
                paused_until = row['paused_until']
            return datetime.now() < paused_until
        except:
            return False
    return False


def pause_bot(duration_seconds: int):
    """Pause bot for specified duration (kill-switch)"""
    paused_until_dt = datetime.fromtimestamp(datetime.now().timestamp() + duration_seconds)
    
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        UPDATE bot_state 
        SET paused_until = {p}, updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (paused_until_dt,))
    conn.commit()
    conn.close()
    print(f"⚠️ Bot paused until {paused_until_dt}")


def get_dm_count_today() -> int:
    """Get number of DMs sent today"""
    conn, _ = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("""
        SELECT total_dms_today, last_dm_date 
        FROM bot_state WHERE id = 1
    """)
    row = cursor.fetchone()
    conn.close()
    
    if row:
        last_date = row['last_dm_date']
        # Convert date object to string if needed
        if not isinstance(last_date, str):
            last_date = last_date.strftime('%Y-%m-%d')
            
        today = datetime.now().strftime('%Y-%m-%d')
        if last_date == today:
            return row['total_dms_today']
    return 0


def increment_dm_count():
    """Increment DM count for today"""
    today = datetime.now().strftime('%Y-%m-%d')
    conn, p = get_connection()
    cursor = get_cursor(conn)
    is_pg = not isinstance(conn, sqlite3.Connection)
    
    # Check if it's a new day
    cursor.execute("SELECT last_dm_date FROM bot_state WHERE id = 1")
    row = cursor.fetchone()
    
    last_date = row['last_dm_date']
    if not isinstance(last_date, str):
        last_date = last_date.strftime('%Y-%m-%d')

    if row and last_date != today:
        # Reset count for new day
        if is_pg:
            cursor.execute(f"UPDATE bot_state SET total_dms_today = 1, last_dm_date = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP WHERE id = 1")
        else:
            cursor.execute(f"UPDATE bot_state SET total_dms_today = 1, last_dm_date = date('now'), updated_at = CURRENT_TIMESTAMP WHERE id = 1")
    else:
        cursor.execute(f"UPDATE bot_state SET total_dms_today = total_dms_today + 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1")
    
    conn.commit()
    conn.close()


def get_account_age_days() -> int:
    """Get account age in days for rate limiting"""
    conn, _ = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("SELECT account_created_date FROM bot_state WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    if row and row['account_created_date']:
        created = row['account_created_date']
        if isinstance(created, str):
            created = datetime.strptime(created, '%Y-%m-%d')
        # If it's already a date object (PG), use it
        return (datetime.now().date() - (created.date() if hasattr(created, 'date') else created)).days
    return 1


def set_account_created_date(date_str: str):
    """Set the account creation date for warmup calculation"""
    conn, p = get_connection()
    cursor = get_cursor(conn)
    cursor.execute(f"""
        UPDATE bot_state 
        SET account_created_date = {p}, updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (date_str,))
    conn.commit()
    conn.close()


# Initialize on import
if __name__ == "__main__":
    init_database()
