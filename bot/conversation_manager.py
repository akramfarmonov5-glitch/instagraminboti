"""
Conversation Manager
Handles multi-turn conversations, state tracking, and scoring
"""
from typing import Optional
from datetime import datetime

from database.models import (
    get_lead_by_username,
    get_conversation,
    get_conversation_history,
    add_message,
    update_conversation_state,
    update_lead_status,
    update_lead_score,
    increment_message_count,
    increment_rejections,
    reset_rejections,
    pause_bot
)
from ai.gemini_client import (
    generate_first_message,
    generate_reply,
    analyze_user_response,
    calculate_score_delta
)
from config import (
    SCORE_THRESHOLD,
    CONSECUTIVE_REJECTIONS_LIMIT,
    KILL_SWITCH_DURATION
)


class ConversationManager:
    """Manages conversation flow, state, and scoring"""
    
    # Conversation states
    STATE_NEW = 'new'
    STATE_FIRST_SENT = 'first_sent'
    STATE_QUALIFYING = 'qualifying'
    STATE_SOFT_TRANSITION = 'soft_transition'
    STATE_REJECTED = 'rejected'
    STATE_CONVERTED = 'converted'
    STATE_EXITED = 'exited'
    
    def __init__(self, username: str):
        self.username = username
        self.lead = get_lead_by_username(username)
        self.conversation = None
        self.history = []
        
        if self.lead:
            self.conversation = get_conversation(self.lead['id'])
            if self.conversation:
                self.history = get_conversation_history(self.conversation['id'])
    
    def get_state(self) -> str:
        """Get current conversation state"""
        if not self.conversation:
            return self.STATE_NEW
        return self.conversation.get('state', self.STATE_NEW)
    
    def get_message_count(self) -> int:
        """Get number of bot messages sent"""
        if not self.conversation:
            return 0
        return self.conversation.get('message_count', 0)
    
    def should_respond(self) -> bool:
        """Check if bot should respond to this user"""
        state = self.get_state()
        
        # Don't respond to rejected/exited conversations
        if state in [self.STATE_REJECTED, self.STATE_EXITED]:
            return False
        
        # Check confidence score
        if self.lead and self.lead.get('confidence_score', 0) < SCORE_THRESHOLD:
            print(f"⚠️ Score too low for {self.username}, exiting")
            self._exit_politely()
            return False
        
        return True
    
    def generate_first_message(self) -> Optional[str]:
        """Generate and track first message"""
        if not self.lead:
            return None
        
        message = generate_first_message(
            bio=self.lead.get('bio', ''),
            last_post_topic=self.lead.get('last_post_topic', ''),
            niche=self.lead.get('niche', 'business')
        )
        
        if message:
            # Save to history
            add_message(self.conversation['id'], 'assistant', message)
            increment_message_count(self.lead['id'])
            update_conversation_state(self.lead['id'], self.STATE_FIRST_SENT)
            update_lead_status(self.username, 'contacted')
            
        return message
    
    def process_user_reply(self, user_message: str) -> Optional[str]:
        """
        Process user's reply and generate response.
        Handles scoring, rejection detection, and state transitions.
        """
        if not self.lead or not self.conversation:
            return None
        
        # Save user message to history
        add_message(self.conversation['id'], 'user', user_message)
        
        # Analyze response
        analysis = analyze_user_response(user_message)
        score_delta = calculate_score_delta(analysis)
        
        # Update score
        update_lead_score(self.username, score_delta)
        print(f"📊 Score delta: {score_delta:+d} for {self.username}")
        
        # Handle rejection
        if analysis['is_rejection']:
            return self._handle_rejection()
        
        # Reset rejection counter on normal response
        reset_rejections(self.username)
        
        # Update state based on message count
        msg_count = self.get_message_count()
        if msg_count >= 3:
            update_conversation_state(self.lead['id'], self.STATE_SOFT_TRANSITION)
        else:
            update_conversation_state(self.lead['id'], self.STATE_QUALIFYING)
        
        # Refresh history
        self.history = get_conversation_history(self.conversation['id'])
        
        # Generate reply
        response = generate_reply(
            conversation_history=self.history,
            lead_info=self.lead
        )
        
        if response:
            add_message(self.conversation['id'], 'assistant', response)
            increment_message_count(self.lead['id'])
        
        return response
    
    def _handle_rejection(self) -> str:
        """Handle rejection - polite exit and kill-switch check"""
        # Increment rejection counter
        rejection_count = increment_rejections(self.username)
        
        # Update state
        update_conversation_state(self.lead['id'], self.STATE_REJECTED)
        update_lead_status(self.username, 'rejected')
        
        # Check for kill-switch trigger
        if rejection_count >= CONSECUTIVE_REJECTIONS_LIMIT:
            print(f"🛑 Kill-switch triggered: {rejection_count} consecutive rejections")
            pause_bot(KILL_SWITCH_DURATION)
        
        # Generate polite exit
        exit_message = "Tushundim, vaqt ajratganingiz uchun rahmat."
        add_message(self.conversation['id'], 'assistant', exit_message)
        
        return exit_message
    
    def _exit_politely(self):
        """Exit conversation politely due to low score"""
        update_conversation_state(self.lead['id'], self.STATE_EXITED)
        update_lead_status(self.username, 'exited')


def get_conversation_manager(username: str) -> ConversationManager:
    """Factory function to get conversation manager for a user"""
    return ConversationManager(username)
