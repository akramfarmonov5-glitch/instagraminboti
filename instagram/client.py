"""
Instagram API Client
Session-first login, DM sending with human delay, inbox monitoring
"""
import json
import time
import random
from pathlib import Path
from typing import Optional, List
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired

from config import (
    INSTAGRAM_USERNAME, 
    INSTAGRAM_PASSWORD,
    SESSION_FILE,
    TYPING_SPEED,
    DELAY_MIN,
    DELAY_MAX
)


class InstagramClient:
    """Instagram API wrapper with session management and human simulation"""
    
    def __init__(self):
        self.client = Client()
        self.logged_in = False
        
    def ensure_logged_in(self) -> bool:
        """Ensure session is valid, login if not"""
        if self.logged_in:
            try:
                # Quick check if session is still alive
                self.client.user_id_from_username("instagram")
                return True
            except:
                self.logged_in = False
        
        print("🔄 Session expired or missing. Re-logging in...")
        return self.login()

    def login(self) -> bool:
        """
        Session-first login strategy.
        Checks Database, then File, finally Password.
        """
        from database.models import get_stored_session, save_stored_session
        
        # 1. Try Loading from Database (Highest priority for Cloud Sync)
        db_session = get_stored_session()
        if db_session:
            print("📦 Found session in database, attempting to load...")
            try:
                session_data = json.loads(db_session)
                self.client.set_settings(session_data)
                self.logged_in = True
                print(f"✅ Database session valid for ID: {self.client.user_id}")
                return True
            except Exception as e:
                print(f"⚠️ Database session invalid: {e}")

        # 2. Try loading from Local File
        if self._load_session():
            print("✅ Loaded existing session from file")
            self._save_session() # Sync to DB immediately
            self.logged_in = True
            return True
        
        # 3. Fall back to password login
        print("🔑 Logging in with password...")
        try:
            self.client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            self._save_session()
            print("✅ Login successful, session synced")
            self.logged_in = True
            return True
        except ChallengeRequired as e:
            print(f"❌ Challenge required: {e}")
            print("Please complete the challenge manually and try again")
            return False
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False
    
    def _load_session(self) -> bool:
        """Load session from file"""
        if not SESSION_FILE.exists():
            return False
        
        try:
            self.client.load_settings(SESSION_FILE)
            if self.client.user_id:
                return True
        except:
            pass
        return False
    
    def _save_session(self):
        """Save session to file AND database"""
        from database.models import save_stored_session
        # Save to file
        try:
            self.client.dump_settings(SESSION_FILE)
        except Exception as e:
            print(f"⚠️ Could not save session to file: {e}")
            
        # Save to database (JSON string)
        try:
            session_data = self.client.get_settings()
            save_stored_session(json.dumps(session_data))
        except Exception as e:
            print(f"⚠️ Could not sync session to database: {e}")
    
    def get_user_info(self, username: str) -> Optional[dict]:
        """Get user profile info using v1 (Mobile API) for stability"""
        try:
            user_id = self.client.user_id_from_username(username)
            info = self.client.user_info_v1(user_id) # Using v1
            return {
                'user_id': user_id,
                'username': info.username,
                'full_name': info.full_name,
                'bio': info.biography,
                'followers': info.follower_count,
                'following': info.following_count,
                'posts_count': info.media_count,
                'is_business': info.is_business,
                'category': info.category if hasattr(info, 'category') else None
            }
        except Exception as e:
            print(f"❌ Failed to get user info for {username}: {e}")
            return None
    
    def get_user_recent_posts(self, username: str, count: int = 3) -> List[dict]:
        """Get user's recent post captions using v1 (Mobile API)"""
        try:
            user_id = self.client.user_id_from_username(username)
            medias = self.client.user_medias_v1(user_id, count) # Using v1
            return [
                {
                    'caption': media.caption_text if media.caption_text else "",
                    'likes': media.like_count,
                    'comments': media.comment_count,
                    'timestamp': media.taken_at
                }
                for media in medias
            ]
        except Exception as e:
            print(f"❌ Failed to get posts for {username}: {e}")
            return []
    
    def get_user_followers(self, username: str, amount: int = 50) -> List[str]:
        """Get followers of a specific user with multiple fallback methods (prioritize v1)"""
        try:
            user_id = self.client.user_id_from_username(username)
            followers = []
            
            # Method 1: v1 (Most stable for authenticated sessions)
            try:
                print(f"📡 Method 1: user_followers_v1...")
                f_list = self.client.user_followers_v1(user_id, amount=amount)
                followers = [f.username for f in f_list]
            except Exception as e:
                print(f"⚠️ Method 1 (v1) failed: {e}")
            
            # Method 2: Fallback to standard if v1 failed
            if not followers:
                try:
                    print(f"📡 Method 2: user_followers (standard)...")
                    f_dict = self.client.user_followers(user_id, amount=amount)
                    followers = [f.username for f in f_dict.values()]
                except Exception as e:
                    print(f"⚠️ Method 2 failed: {e}")
            
            return followers
        except Exception as e:
            print(f"❌ Failed to resolve user_id for {username}: {e}")
            return []

    def get_post_likers(self, username: str, amount: int = 50) -> List[str]:
        """Get usernames of users who liked the most recent post (using v1 fallback)"""
        try:
            user_id = self.client.user_id_from_username(username)
            # Try getting media using v1
            medias = self.client.user_medias_v1(user_id, amount=1)
            if not medias:
                return []
            
            media_id = medias[0].id
            # media_likers uses a stable endpoint
            likers = self.client.media_likers(media_id)
            return [user.username for user in likers[:amount]]
        except Exception as e:
            print(f"❌ Failed to get post likers for {username}: {e}")
            return []

    def search_users_by_query(self, query: str, amount: int = 20) -> List[str]:
        """Search profiles by keyword using v1 for stability"""
        self.ensure_logged_in()
        try:
            print(f"🔎 Searching for keyword: {query}")
            # search_users_v1 requires 'count'
            users = self.client.search_users_v1(query, count=amount)
            return [user.username for user in users]
        except Exception as e:
            print(f"❌ Keyword search failed for '{query}': {e}")
            return []

    def get_location_feed(self, location_name: str, amount: int = 20) -> List[str]:
        """Get usernames from a specific location using v1 for media"""
        self.ensure_logged_in()
        try:
            print(f"📍 Searching for location: {location_name}")
            # fbsearch_places is the correct method name
            locations = self.client.fbsearch_places(location_name)
            if not locations:
                return []
            
            # Use the first location match
            location = locations[0]
            # Use v1 for media fetching for better stability
            medias = self.client.location_medias_v1(location.pk, amount=amount)
            return [media.user.username for media in medias]
        except Exception as e:
            print(f"❌ Location search failed for '{location_name}': {e}")
            return []

    def get_hashtag_feed(self, hashtag: str, amount: int = 20) -> List[str]:
        """Get usernames from a specific hashtag using v1"""
        self.ensure_logged_in()
        try:
            # Remove # if present
            tag = hashtag.replace("#", "")
            print(f"🏷️ Searching for hashtag: #{tag}")
            medias = self.client.hashtag_medias_v1(tag, amount=amount)
            return [media.user.username for media in medias]
        except Exception as e:
            print(f"❌ Hashtag search failed for '#{hashtag}': {e}")
            return []

    def top_search_leads(self, query: str) -> List[str]:
        """Search using the top/search endpoint (v1)"""
        self.ensure_logged_in()
        try:
            print(f"🔦 Top Search for: {query}")
            results = self.client.top_search(query)
            usernames = []
            
            # Extract from users
            if 'users' in results:
                for u in results['users']:
                    usernames.append(u['user']['username'])
            
            # Extract from hashtags (take recent media owners)
            if 'hashtags' in results:
                for h in results['hashtags'][:2]:
                    usernames.extend(self.get_hashtag_feed(h['hashtag']['name'], amount=5))
            
            return usernames
        except Exception as e:
            print(f"❌ Top search failed for '{query}': {e}")
            return []

    def get_suggested_users(self, username: str, amount: int = 15) -> List[str]:
        """Get similar account recommendations using v1 search_related_profiles"""
        try:
            print(f"🔗 Getting suggestions for: {username}")
            user_id = self.client.user_id_from_username(username)
            # instagrapi usually handles this via v1 automatically if using v1 methods
            suggestions = self.client.search_related_profiles(user_id)
            return [user.username for user in suggestions[:amount]]
        except Exception as e:
            print(f"❌ Suggestions failed for {username}: {e}")
            return []

    def send_dm(self, username: str, message: str) -> bool:
        """
        Send DM with human typing delay simulation.
        Delay formula: len(message) * TYPING_SPEED + random(DELAY_MIN, DELAY_MAX)
        """
        if not self.logged_in:
            print("❌ Not logged in")
            return False
        
        # Calculate human-like delay
        typing_time = len(message) * TYPING_SPEED
        random_delay = random.uniform(DELAY_MIN, DELAY_MAX)
        total_delay = typing_time + random_delay
        
        print(f"⏳ Simulating typing delay: {total_delay:.1f}s")
        time.sleep(total_delay)
        
        try:
            user_id = self.client.user_id_from_username(username)
            self.client.direct_send(message, [user_id])
            print(f"✅ DM sent to {username}")
            return True
        except Exception as e:
            print(f"❌ Failed to send DM to {username}: {e}")
            return False
    
    def get_unread_messages(self) -> List[dict]:
        """Get unread direct messages"""
        try:
            threads = self.client.direct_threads(amount=20)
            unread = []
            
            for thread in threads:
                # Log all threads for debugging
                thread_user = thread.users[0].username if thread.users else 'unknown'
                # print(f"🔍 Found thread with: {thread_user}") # Verbose
                
                # Check for unread messages or last message not from us
                if thread.messages:
                    last_msg = thread.messages[0]
                    # Check if last message is from the other user (not us)
                    if str(last_msg.user_id) != str(self.client.user_id):
                        print(f"📩 New message from {thread_user}")
                        unread.append({
                                'thread_id': thread.id,
                                'username': thread_user,
                                'message': last_msg.text if last_msg.text else "",
                                'timestamp': last_msg.timestamp
                            })
            
            return unread
        except Exception as e:
            print(f"❌ Failed to get messages: {e}")
            return []
    
    def get_thread_messages(self, thread_id: str, count: int = 10) -> List[dict]:
        """Get messages from a specific thread"""
        try:
            thread = self.client.direct_thread(thread_id)
            return [
                {
                    'user_id': str(msg.user_id),
                    'text': msg.text if msg.text else "",
                    'timestamp': msg.timestamp,
                    'is_me': str(msg.user_id) == str(self.client.user_id)
                }
                for msg in thread.messages[:count]
            ]
        except Exception as e:
            print(f"❌ Failed to get thread messages: {e}")
            return []
    
    def logout(self):
        """Logout and clear session"""
        try:
            self.client.logout()
            self.logged_in = False
            print("✅ Logged out")
        except Exception as e:
            print(f"⚠️ Logout error: {e}")


# Singleton instance
_client: Optional[InstagramClient] = None

def get_instagram_client() -> InstagramClient:
    """Get or create Instagram client instance"""
    global _client
    if _client is None:
        _client = InstagramClient()
    return _client
