"""
Gemini AI Client
Conversation generation and niche detection
"""
import google.generativeai as genai
from typing import Optional, List

from config import GEMINI_API_KEY, get_time_of_day
from ai.prompts import (
    SYSTEM_PROMPT,
    NICHE_DETECTION_PROMPT,
    get_first_message_prompt,
    get_reply_prompt
)


# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)


def get_model():
    """Get Gemini Flash model (fast and efficient)"""
    return genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT
    )


def detect_niche(bio: str, last_post: str) -> str:
    """
    Detect lead's niche using AI.
    Returns: business, ecommerce, services, or personal_brand
    """
    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        prompt = NICHE_DETECTION_PROMPT.format(bio=bio, last_post=last_post)
        response = model.generate_content(prompt)
        
        niche = response.text.strip().lower()
        valid_niches = ['business', 'ecommerce', 'services', 'personal_brand']
        
        if niche in valid_niches:
            return niche
        return 'business'  # Default fallback
    except Exception as e:
        print(f"⚠️ Niche detection failed: {e}")
        return 'business'


def generate_first_message(bio: str, last_post_topic: str, niche: str) -> str:
    """
    Generate first DM message for a lead.
    Uses profile info to create personalized opener.
    """
    try:
        model = get_model()
        time_of_day = get_time_of_day()
        
        prompt = get_first_message_prompt(bio, last_post_topic, niche, time_of_day)
        response = model.generate_content(prompt)
        
        message = response.text.strip()
        # Remove any quotes if present
        message = message.strip('"\'')
        
        return message
    except Exception as e:
        print(f"❌ Message generation failed: {e}. Using fallback.")
        templates = {
            "morning": "Assalomu alaykum! Ishlaringiz va biznesingiz yaxshimi? Akkauntingizni kuzatib qiziq mavzularni ko'rdim.",
            "afternoon": "Assalomu alaykum! Biznesingiz rivoji qanday ketyapti? Profilingizdagi kontentlar juda qiziqarli ekan.",
            "evening": "Assalomu alaykum! Xayrli kech. Ishlaringiz yaxshimi? Profilingizni ko'rib juda qiziqib qoldim."
        }
        time_of_day = get_time_of_day()
        return templates.get(time_of_day, "Assalomu alaykum! Ishlaringiz yaxshimi? Profilingizni kuzatib juda qiziqib qoldim.")


def generate_reply(conversation_history: List[dict], lead_info: dict) -> str:
    """
    Generate reply based on conversation history.
    Handles qualification, rejection detection, and soft transition.
    """
    try:
        model = get_model()
        time_of_day = get_time_of_day()
        
        prompt = get_reply_prompt(conversation_history, lead_info, time_of_day)
        response = model.generate_content(prompt)
        
        message = response.text.strip()
        message = message.strip('"\'')
        
        return message
    except Exception as e:
        print(f"❌ Reply generation failed: {e}")
        return ""


def analyze_user_response(message: str) -> dict:
    """
    Analyze user's response to determine intent and scoring.
    Returns dict with: is_rejection, is_question, mentions_problem, is_cold
    """
    message_lower = message.lower().strip()
    
    # Rejection indicators
    rejection_phrases = [
        'kerak emas', 'qiziq emas', "yo'q", 'rahmat lekin',
        'hozir emas', 'vaqtim yo\'q', 'boshqa safar', 'spam'
    ]
    is_rejection = any(phrase in message_lower for phrase in rejection_phrases)
    
    # Question indicators (they're engaged)
    is_question = '?' in message
    
    # Problem mention indicators
    problem_phrases = [
        'muammo', 'qiyin', 'vaqt', 'ketadi', 'umuman',
        'yordam', 'kerak', 'qanday', 'nima qilsam'
    ]
    mentions_problem = any(phrase in message_lower for phrase in problem_phrases)
    
    # Engagement indicators
    neutral_engagement = ['ok', 'ha', 'yoq', 'hmm', 'xop', 'bilmadim', 'ko\'ramiz']
    is_neutral = message_lower in neutral_engagement or len(message) < 10
    
    return {
        'is_rejection': is_rejection,
        'is_question': is_question,
        'mentions_problem': mentions_problem,
        'is_cold': is_neutral  # Renaming for backward compatibility in calculate_score_delta
    }


def calculate_score_delta(analysis: dict) -> int:
    """
    Calculate confidence score change based on response analysis.
    Uses scoring from config.
    """
    from config import (
        SCORE_ASKED_QUESTION,
        SCORE_MENTIONED_PROBLEM,
        SCORE_SHORT_COLD_REPLY,
        SCORE_REJECTION
    )
    
    score = 0
    
    if analysis['is_rejection']:
        score += SCORE_REJECTION  # -5
    elif analysis['is_cold']:
        # If it's just a short/neutral response, don't penalize yet, give AI pivot a chance
        score += 0  
    else:
        if analysis['is_question']:
            score += SCORE_ASKED_QUESTION  # +1
        if analysis['mentions_problem']:
            score += SCORE_MENTIONED_PROBLEM  # +2
    
    return score
