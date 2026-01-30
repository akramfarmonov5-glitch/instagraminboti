"""
Bot Scheduler
Handles automation, rate limiting, and periodic tasks
"""
import time
import random
from datetime import datetime

from config import (
    DM_LIMITS,
    INBOX_CHECK_MIN,
    INBOX_CHECK_MAX
)
from database.models import (
    init_database,
    is_bot_paused,
    get_dm_count_today,
    get_account_age_days,
    increment_dm_count,
    get_leads_by_status,
    add_lead
)
from instagram.client import get_instagram_client
from instagram.scraper import scrape_lead
from bot.conversation_manager import get_conversation_manager


def get_daily_dm_limit() -> int:
    """Get DM limit based on account age (gradual warmup)"""
    days = get_account_age_days()
    
    for (min_day, max_day), limit in DM_LIMITS.items():
        if min_day <= days <= max_day:
            return limit
    
    return 8  # Default safe limit


def can_send_dm() -> bool:
    """Check if bot can send a DM (rate limiting + pause check)"""
    # Check kill-switch
    if is_bot_paused():
        print("⏸️ Bot is paused (kill-switch active)")
        return False
    
    # Check daily limit
    sent_today = get_dm_count_today()
    limit = get_daily_dm_limit()
    
    if sent_today >= limit:
        print(f"📊 Daily limit reached: {sent_today}/{limit}")
        return False
    
    print(f"📊 DM count: {sent_today}/{limit}")
    return True


def process_new_leads():
    """Send first message to new leads"""
    if not can_send_dm():
        return
    
    client = get_instagram_client()
    if not client.logged_in:
        if not client.login():
            return
    
    # Get leads that haven't been contacted
    new_leads = get_leads_by_status('new')
    
    for lead in new_leads:
        if not can_send_dm():
            break
        
        username = lead['username']
        print(f"\n📤 Processing lead: {username}")
        
        manager = get_conversation_manager(username)
        message = manager.generate_first_message()
        
        if message:
            success = client.send_dm(username, message)
            if success:
                increment_dm_count()
                print(f"✅ First message sent to {username}")
            else:
                print(f"❌ Failed to send to {username}")
        
        # Random delay between leads
        delay = random.uniform(30, 90)
        print(f"⏳ Waiting {delay:.0f}s before next lead...")
        time.sleep(delay)


def process_inbox():
    """Check inbox and respond to messages"""
    client = get_instagram_client()
    if not client.logged_in:
        if not client.login():
            return
    
    print("\n📥 Checking inbox...")
    unread = client.get_unread_messages()
    
    for msg in unread:
        if not can_send_dm():
            break
        
        username = msg['username']
        user_message = msg['message']
        
        print(f"\n💬 Reply from {username}: {user_message[:50]}...")
        
        manager = get_conversation_manager(username)
        
        if not manager.should_respond():
            print(f"⏭️ Skipping {username} (should not respond)")
            continue
        
        response = manager.process_user_reply(user_message)
        
        if response:
            success = client.send_dm(username, response)
            if success:
                increment_dm_count()
                print(f"✅ Reply sent to {username}")
            else:
                print(f"❌ Failed to reply to {username}")
        
        # Delay between replies
        delay = random.uniform(20, 60)
        time.sleep(delay)


def get_random_interval() -> int:
    """Get random interval for inbox checking (7-12 min)"""
    return random.randint(INBOX_CHECK_MIN, INBOX_CHECK_MAX)


def run_scheduler():
    """Main scheduler loop"""
    print("🤖 Starting Instagram DM Bot Scheduler")
    print(f"📊 Daily limit: {get_daily_dm_limit()} DMs")
    
    client = get_instagram_client()
    if not client.login():
        print("❌ Failed to login, exiting")
        return
    
    while True:
        try:
            # Check if paused
            if is_bot_paused():
                print("⏸️ Bot is paused, waiting...")
                time.sleep(3600)  # Check again in 1 hour
                continue
            
            # Process new leads (send first messages)
            process_new_leads()
            
            # Process inbox (reply to messages)
            process_inbox()
            
            # Wait random interval
            interval = get_random_interval()
            print(f"\n⏳ Next check in {interval // 60} minutes...")
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
            break
        except Exception as e:
            print(f"❌ Error in scheduler: {e}")
            time.sleep(300)  # Wait 5 min on error


def add_leads_from_list(usernames: list):
    """Add leads from a list of usernames (with scraping)"""
    client = get_instagram_client()
    if not client.login():
        print("❌ Failed to login")
        return
    
    for username in usernames:
        print(f"\n📊 Scraping {username}...")
        lead_data = scrape_lead(username)
        
        if lead_data:
            add_lead(
                username=lead_data['username'],
                bio=lead_data.get('bio', ''),
                last_post_topic=lead_data.get('last_post_topic', ''),
                niche=lead_data.get('niche', 'business')
            )
            print(f"✅ Added lead: {username} ({lead_data.get('niche')})")
        else:
            print(f"⚠️ Failed to scrape {username}")
        
        # Delay between scrapes
        time.sleep(random.uniform(3, 8))


def scrape_followers_of_user(target_username: str, amount: int = 50):
    """Scrape leads from an influencer's followers and likers"""
    client = get_instagram_client()
    if not client.login():
        print("❌ Failed to login")
        return
    
    combined_leads = []
    
    # Try followers
    print(f"\n🔍 Step 1: Fetching followers of {target_username}...")
    combined_leads.extend(client.get_user_followers(target_username, amount=amount // 2))
    
    # Try likers (often more active/public)
    print(f"🔍 Step 2: Fetching post likers of {target_username}...")
    combined_leads.extend(client.get_post_likers(target_username, amount=amount // 2))
    
    # Remove duplicates
    unique_leads = list(set(combined_leads))
    print(f"👥 Found {len(unique_leads)} potential unique leads.")
    
    if not unique_leads:
        print("⚠️ No leads found. Check if the account is public or if you are rate-limited.")
        return

    added_count = 0
    for username in unique_leads:
        print(f"📊 Analyzing: {username}...")
        
        # Scrape and filter
        lead_data = scrape_lead(username)
        
        if lead_data and lead_data.get('is_business'):
            add_lead(
                username=lead_data['username'],
                bio=lead_data.get('bio', ''),
                last_post_topic=lead_data.get('last_post_topic', ''),
                niche=lead_data.get('niche', 'business')
            )
            print(f"✅ Added BUSINESS lead: {username}")
            added_count += 1
        else:
            reason = "not business/private" if lead_data else "scraping failed"
            print(f"⏭️ Skipping {username} ({reason})")
        
        # Human-like delay between leads to avoid blocks
        time.sleep(random.uniform(10, 20))
    
    print(f"\n✨ Finished! Added {added_count} active leads from {target_username}")


def discover_new_leads(query: str = None, amount: int = 50):
    """
    Robust discovery using a 'Suggestion Tree'.
    Starts from seed Uzbek business accounts and traverses recommendations.
    """
    client = get_instagram_client()
    if not client.login():
        print("❌ Failed to login")
        return
    
    # 1. Seed accounts (Top Uzbek business figures)
    seeds = [
        'alisherisaev_uz', 'ibrohim_gulyamov', 'akmalabdullaev_uz', 
        'asror.iskandarov', 'shukurullo_isroilov_official', 
        'temur_adhamov', 'zohid_mamatov'
    ]
    
    # If user provided a query, add it as a seed if it's a username
    if query and not " " in query:
        seeds.insert(0, query)

    print(f"\n🌳 Starting Discovery Tree from {len(seeds)} seed accounts...")
    
    potential_usernames = []
    
    # Track who we already expanded to avoid loops
    expanded_seeds = set()
    
    for seed in seeds[:3]: # Limit seeds per run to avoid blocks
        print(f"📍 Expanding from seed: {seed}...")
        
        # Get suggestions
        suggestions = client.get_suggested_users(seed, amount=20)
        potential_usernames.extend(suggestions)
        expanded_seeds.add(seed)
        
        # Deep expansion (Step 2)
        if len(potential_usernames) < amount:
            for sub_seed in suggestions[:3]:
                if sub_seed not in expanded_seeds:
                    print(f"  └─ Deep expansion: {sub_seed}...")
                    sub_suggestions = client.get_suggested_users(sub_seed, amount=10)
                    potential_usernames.extend(sub_suggestions)
                    expanded_seeds.add(sub_seed)
                    time.sleep(random.uniform(5, 10))
    
    # Deduplicate
    unique_usernames = list(set(potential_usernames))
    print(f"✅ Discovery phase complete. Found {len(unique_usernames)} unique profiles to analyze.")
    
    added_count = 0
    for username in unique_usernames[:amount]:
        if username in seeds: continue # Skip seeds
        
        print(f"📊 Analyzing: {username}...")
        lead_data = scrape_lead(username)
        
        if lead_data and lead_data.get('is_business'):
            add_lead(
                username=lead_data['username'],
                bio=lead_data.get('bio', ''),
                last_post_topic=lead_data.get('last_post_topic', ''),
                niche=lead_data.get('niche', 'business')
            )
            print(f"✅ Added BUSINESS lead: {username}")
            added_count += 1
        else:
            reason = "not business/private" if lead_data else "scraping failed"
            print(f"⏭️ Skipping {username} ({reason})")
        
        # Protect account
        time.sleep(random.uniform(10, 20))
    
def discover_all_uzbek_businesses(amount_per_source: int = 20):
    """
    Broad discovery cycling through top Uzbek business influencers.
    This is the most reliable way to find businesses in Uzbekistan.
    """
    influencers = [
        'alisherisaev_uz', 'ibrohim_gulyamov', 'akmalabdullaev_uz', 
        'asror.iskandarov', 'shukurullo_isroilov_official', 
        'temur_adhamov', 'zohid_mamatov', 'aziz_saidov_official',
        'abbos_baxtiyorovich', 'muhammadali_eshonqulov',
        'jahongir_artikhodjayev_official', 'murod_nazarov_official'
    ]
    
    print(f"\n🌍 Starting Global Uzbek Business Discovery ({len(influencers)} sources)...")
    
    for influencer in influencers:
        print(f"\n🎬 Source: @{influencer}")
        scrape_followers_of_user(influencer, amount=amount_per_source)
        
        # Long delay between sources to stay safe
        wait_time = random.uniform(30, 60)
        print(f"⏳ Waiting {wait_time:.1f}s before next source...")
        time.sleep(wait_time)
    
    print("\n✨ Global discovery cycle complete!")
