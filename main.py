"""
Instagram DM Sales Agent Bot
Main entry point
"""
import sys
from datetime import datetime

import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from config import validate_config, DATA_DIR
from database.models import init_database, set_account_created_date
from bot.scheduler import run_scheduler, add_leads_from_list, scrape_followers_of_user, discover_new_leads, discover_all_uzbek_businesses


class PingHandler(BaseHTTPRequestHandler):
    """Simple handler for keep-alive pings"""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        # Silent logs for pings
        return

def start_keep_alive_server(port=8080):
    """Run a simple HTTP server in the background for UptimeRobot"""
    server = HTTPServer(('0.0.0.0', port), PingHandler)
    print(f"🌐 Keep-alive server started on port {port}")
    server.serve_forever()


def print_banner():
    """Print startup banner"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║          Instagram DM Sales Agent Bot                     ║
║          Gemini AI + Automatic Lead Qualification         ║
╚═══════════════════════════════════════════════════════════╝
    """)


def main():
    """Main entry point"""
    print_banner()
    
    # Validate configuration
    if not validate_config():
        print("\n❌ Please configure your .env file first!")
        print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)
    
    # Initialize database
    init_database()
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "add":
            # Add leads: python main.py add username1 username2 ...
            usernames = sys.argv[2:]
            if usernames:
                print(f"📋 Adding {len(usernames)} leads...")
                add_leads_from_list(usernames)
            else:
                print("Usage: python main.py add username1 username2 ...")
        
        elif command == "set-date":
            # Set account creation date: python main.py set-date 2024-01-01
            if len(sys.argv) > 2:
                date_str = sys.argv[2]
                set_account_created_date(date_str)
                print(f"✅ Account creation date set to: {date_str}")
            else:
                print("Usage: python main.py set-date YYYY-MM-DD")
        
        elif command == "scrape-followers":
            # Scrape followers: python main.py scrape-followers source_username [amount]
            if len(sys.argv) > 2:
                source_user = sys.argv[2]
                amount = int(sys.argv[3]) if len(sys.argv) > 3 else 50
                scrape_followers_of_user(source_user, amount)
            else:
                print("Usage: python main.py scrape-followers source_username [amount]")
        
        elif command == "discover":
            # Discover leads: python main.py discover "keyword" [amount]
            if len(sys.argv) > 2:
                query = sys.argv[2]
                amount = int(sys.argv[3]) if len(sys.argv) > 3 else 20
                discover_new_leads(query, amount)
            else:
                print("Usage: python main.py discover \"keyword\" [amount]")
        
        elif command == "discover-all":
            # Discover from all seeds: python main.py discover-all [amount_per_source]
            amount = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            discover_all_uzbek_businesses(amount)
        
        elif command == "run":
            # Start keep-alive server in background
            port = int(os.getenv("PORT", 8080))
            threading.Thread(target=start_keep_alive_server, args=(port,), daemon=True).start()
            
            # Run the scheduler
            run_scheduler()
        
        else:
            print_help()
    else:
        print_help()


def print_help():
    """Print usage help"""
    print("""
📚 Usage:

  python main.py run                    - Start the bot scheduler
  python main.py add user1 user2 ...    - Add leads (scrapes profiles)
  python main.py scrape-followers user [N] - Scrape N followers from a user
  python main.py set-date YYYY-MM-DD    - Set account creation date (for warmup)

📝 Setup:
  1. Copy .env.example to .env
  2. Add your Gemini API key
  3. Add your Instagram test account credentials
  4. Run: python main.py set-date 2024-01-25  (your account's creation date)
  5. Scrape leads: python main.py scrape-followers alisherisaev_uz 50
  6. Start bot: python main.py run

⚠️ Warning: Use a TEST account only! Main account may get banned.
    """)


if __name__ == "__main__":
    main()
