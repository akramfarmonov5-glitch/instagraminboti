"""
Lead Scraper
Scrapes Instagram profiles and detects niche using AI
"""
from typing import Optional, List
from instagram.client import get_instagram_client
from ai.gemini_client import detect_niche


def scrape_lead(username: str) -> Optional[dict]:
    """
    Scrape lead information from Instagram profile.
    Returns dict with bio, last_post_topic, and detected niche.
    """
    client = get_instagram_client()
    
    # Get user info
    user_info = client.get_user_info(username)
    if not user_info:
        return None
    
    # Get recent posts
    posts = client.get_user_recent_posts(username, count=3)
    last_post_topic = ""
    if posts and posts[0].get('caption'):
        last_post_topic = posts[0]['caption'][:200]  # First 200 chars
    
    # Detect niche using AI
    niche = detect_niche(user_info.get('bio', ''), last_post_topic)
    
    return {
        'username': username,
        'bio': user_info.get('bio', ''),
        'last_post_topic': last_post_topic,
        'niche': niche,
        'followers': user_info.get('followers', 0),
        'is_business': user_info.get('is_business', False)
    }


def scrape_leads_from_list(usernames: List[str]) -> List[dict]:
    """Scrape multiple leads from a list of usernames"""
    leads = []
    for username in usernames:
        print(f"📊 Scraping {username}...")
        lead = scrape_lead(username)
        if lead:
            leads.append(lead)
    return leads


def load_usernames_from_csv(filepath: str) -> List[str]:
    """Load usernames from a CSV file (one username per line)"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        return [line.strip() for line in lines if line.strip()]
    except Exception as e:
        print(f"❌ Failed to load CSV: {e}")
        return []
