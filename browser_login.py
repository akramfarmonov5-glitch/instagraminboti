"""
Cookie debugger - barcha cookie'larni ko'rsatadi
"""
from playwright.sync_api import sync_playwright
import json
from pathlib import Path
from urllib.parse import unquote

DATA_DIR = Path(__file__).parent / "data"
SESSION_FILE = DATA_DIR / "session.json"


def debug_cookies():
    print("""
╔═══════════════════════════════════════════════════════════╗
║          Cookie Debug - barcha cookie'larni ko'rsatish   ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    DATA_DIR.mkdir(exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("📱 Instagram login sahifasi ochilmoqda...")
        page.goto("https://www.instagram.com/accounts/login/")
        
        print("\n⏳ Brauzerda login qiling...")
        print("   Username: botfactory1")
        print("   Password: Gisobot201415")
        print("\n✅ HOME sahifa ko'ringach Enter bosing...")
        
        input()
        
        # Barcha cookie'larni olish va ko'rsatish
        cookies = context.cookies()
        
        print(f"\n📋 Jami {len(cookies)} ta cookie topildi:\n")
        
        session_data = {"cookies": {}}
        
        for cookie in cookies:
            name = cookie['name']
            value = cookie['value']
            domain = cookie.get('domain', '')
            
            # Muhim cookie'larni ajratib ko'rsatamiz
            if name in ['sessionid', 'csrftoken', 'ds_user_id', 'mid', 'rur', 'ig_did']:
                print(f"  ⭐ {name}: {value[:50]}..." if len(value) > 50 else f"  ⭐ {name}: {value}")
            
            session_data["cookies"][name] = value
        
        # Maxsus session ma'lumotlarini olish
        session_id = session_data["cookies"].get('sessionid')
        csrf_token = session_data["cookies"].get('csrftoken')
        ds_user_id = session_data["cookies"].get('ds_user_id')
        
        print(f"\n📊 Muhim ma'lumotlar:")
        print(f"   sessionid: {session_id}")
        print(f"   csrftoken: {csrf_token}")
        print(f"   ds_user_id: {ds_user_id}")
        
        if session_id:
            # To'liq session yaratish
            full_session = {
                "uuids": {
                    "phone_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "uuid": "12345678-1234-1234-1234-123456789012",
                    "client_session_id": "session",
                    "advertising_id": "ad-id",
                    "android_device_id": "android_1234567890abcdef",
                    "request_id": "request"
                },
                "mid": session_data["cookies"].get("mid", ""),
                "ig_u_rur": session_data["cookies"].get("rur"),
                "ig_www_claim": None,
                "authorization_data": {
                    "ds_user_id": ds_user_id or "",
                    "sessionid": unquote(session_id) if session_id else ""
                },
                "cookies": session_data["cookies"],
                "last_login": None,
                "device_settings": {
                    "app_version": "269.0.0.18.75",
                    "android_version": 26,
                    "android_release": "8.0.0",
                    "dpi": "480dpi",
                    "resolution": "1080x1920",
                    "manufacturer": "samsung",
                    "device": "SM-G950F",
                    "model": "star2lte",
                    "cpu": "exynos8895",
                    "version_code": "314665256"
                },
                "user_agent": "Instagram 269.0.0.18.75 Android"
            }
            
            with open(SESSION_FILE, 'w') as f:
                json.dump(full_session, f, indent=2)
            
            print(f"\n✅ Session saqlandi: {SESSION_FILE}")
            print("\n🚀 Endi 'python main.py run' bilan botni ishga tushiring!")
        else:
            print("\n❌ sessionid topilmadi!")
            print("   Ehtimol siz hali login qilmagansiz yoki")
            print("   Instagram cookie'larni boshqacha saqlayapti.")
            print("\n📋 Barcha cookie nomlari:")
            for name in session_data["cookies"].keys():
                print(f"   - {name}")
        
        browser.close()


if __name__ == "__main__":
    debug_cookies()
