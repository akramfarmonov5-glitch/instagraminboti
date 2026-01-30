"""
Session-based Login Helper
Bu skript brauzerdan olingan session bilan login qiladi
"""
from instagrapi import Client
from pathlib import Path
import json

DATA_DIR = Path(__file__).parent / "data"
SESSION_FILE = DATA_DIR / "session.json"


def login_with_session_id(session_id: str, csrf_token: str, username: str):
    """
    Brauzerdan olingan session bilan login qilish
    
    Session ID va CSRF token'ni brauzerdan olish:
    1. Instagram.com ga kiring
    2. F12 (Developer Tools) oching
    3. Application > Cookies > instagram.com
    4. sessionid va csrftoken qiymatlarini nusxalang
    """
    cl = Client()
    
    # Session settings
    cl.set_settings({
        "authorization_data": {
            "ds_user_id": "",  # Bu avtomatik olinadi
            "sessionid": session_id,
            "csrftoken": csrf_token,
        },
        "cookies": {
            "sessionid": session_id,
            "csrftoken": csrf_token,
        },
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    try:
        # Test the session
        user_info = cl.account_info()
        print(f"✅ Session login successful!")
        print(f"   Username: {user_info.username}")
        print(f"   Full name: {user_info.full_name}")
        
        # Save session for future use
        DATA_DIR.mkdir(exist_ok=True)
        cl.dump_settings(SESSION_FILE)
        print(f"✅ Session saved to {SESSION_FILE}")
        
        return cl
    except Exception as e:
        print(f"❌ Session login failed: {e}")
        return None


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║          Instagram Session Login Helper                   ║
╚═══════════════════════════════════════════════════════════╝

Session ID va CSRF Token olish uchun:

1. Brauzerda instagram.com ga kiring (botfactory1 bilan)
2. F12 bosing (Developer Tools)
3. Application tabiga o'ting
4. Cookies > instagram.com tanlang
5. Quyidagi qiymatlarni nusxalang:
   - sessionid
   - csrftoken

""")
    
    session_id = input("sessionid kiriting: ").strip()
    csrf_token = input("csrftoken kiriting: ").strip()
    username = input("username kiriting (botfactory1): ").strip() or "botfactory1"
    
    if session_id and csrf_token:
        client = login_with_session_id(session_id, csrf_token, username)
        if client:
            print("\n✅ Tayyor! Endi 'python main.py run' bilan botni ishga tushiring.")
    else:
        print("❌ Session ID yoki CSRF token kiritilmadi")


if __name__ == "__main__":
    main()
