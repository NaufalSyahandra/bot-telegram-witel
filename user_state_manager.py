import logging
import time
from typing import Dict, List, Optional
from constants import UserState, KendalaType

logger = logging.getLogger(__name__)


class UserStateManager:
    """User state management class"""

    def __init__(self):
        self.user_states: Dict[int, Dict] = {}

    def _ensure_user_data(self, chat_id: int):
        """Ensure user data structure exists"""
        if chat_id not in self.user_states:
            self.user_states[chat_id] = {
                'state': UserState.IDLE,
                'kendala_type': None,
                'parsed_data': None,
                'last_row': 0,
                'sheet_name': None,  # NEW: Track which sheet was used
                'media_urls': {},
                'media_step': 0,
                'last_activity': time.time()
            }

    def set_user_state(self, chat_id: int, state: UserState):
        """Set user state"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['state'] = state
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} state set to {state.value}")

    def get_user_state(self, chat_id: int) -> UserState:
        """Get user state"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['state']

    def set_user_kendala_type(self, chat_id: int, kendala_type: KendalaType):
        """Set user kendala type"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['kendala_type'] = kendala_type
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} kendala type set to {kendala_type.value}")

    def get_user_kendala_type(self, chat_id: int) -> Optional[KendalaType]:
        """Get user kendala type"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['kendala_type']

    def set_user_parsed_data(self, chat_id: int, parsed_data: Dict):
        """Set user parsed data"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['parsed_data'] = parsed_data
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} parsed data set")

    def get_user_parsed_data(self, chat_id: int) -> Optional[Dict]:
        """Get user parsed data"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['parsed_data']

    def set_user_last_row(self, chat_id: int, last_row: int):
        """Set user last row number"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['last_row'] = last_row
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} last row set to {last_row}")

    def get_user_last_row(self, chat_id: int) -> int:
        """Get user last row number"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['last_row']

    def set_user_sheet_name(self, chat_id: int, sheet_name: str):
        """Set user sheet name"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['sheet_name'] = sheet_name
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} sheet name set to {sheet_name}")

    def get_user_sheet_name(self, chat_id: int) -> Optional[str]:
        """Get user sheet name"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['sheet_name']

    def add_user_media_url(self, chat_id: int, field_name: str, media_url: str):
        """Add media URL to user data"""
        self._ensure_user_data(chat_id)
        
        if field_name not in self.user_states[chat_id]['media_urls']:
            self.user_states[chat_id]['media_urls'][field_name] = []
        
        self.user_states[chat_id]['media_urls'][field_name].append(media_url)
        self.user_states[chat_id]['last_activity'] = time.time()
        
        logger.info(f"User {chat_id} added media URL for {field_name}: {media_url}")

    def get_user_media_urls(self, chat_id: int) -> Dict[str, List[str]]:
        """Get user media URLs"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['media_urls']

    def get_user_media_count(self, chat_id: int) -> int:
        """Get total count of user media"""
        media_urls = self.get_user_media_urls(chat_id)
        total = sum(len(urls) for urls in media_urls.values())
        return total

    def set_user_media_step(self, chat_id: int, step: int):
        """Set user media step"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['media_step'] = step
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} media step set to {step}")

    def get_user_media_step(self, chat_id: int) -> int:
        """Get user media step"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['media_step']

    def increment_user_media_step(self, chat_id: int):
        """Increment user media step"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['media_step'] += 1
        self.user_states[chat_id]['last_activity'] = time.time()
        new_step = self.user_states[chat_id]['media_step']
        logger.info(f"User {chat_id} media step incremented to {new_step}")

    def clear_user_data(self, chat_id: int):
        """Clear all user data"""
        if chat_id in self.user_states:
            # Keep only basic structure
            self.user_states[chat_id] = {
                'state': UserState.IDLE,
                'kendala_type': None,
                'parsed_data': None,
                'last_row': 0,
                'sheet_name': None,
                'media_urls': {},
                'media_step': 0,
                'last_activity': time.time()
            }
            logger.info(f"User {chat_id} data cleared")

    def check_rate_limit(self, chat_id: int, rate_limit_seconds: int) -> bool:
        """Check if user is rate limited"""
        self._ensure_user_data(chat_id)
        
        current_time = time.time()
        last_activity = self.user_states[chat_id]['last_activity']
        
        if current_time - last_activity < rate_limit_seconds:
            logger.warning(f"User {chat_id} rate limited")
            return False
        
        self.user_states[chat_id]['last_activity'] = current_time
        return True

    def debug_user_state(self, chat_id: int):
        """Debug user state information"""
        if chat_id in self.user_states:
            user_data = self.user_states[chat_id]
            logger.debug(
                f"User {chat_id} debug - State: {user_data['state'].value}, "
                f"Kendala: {user_data['kendala_type'].value if user_data['kendala_type'] else None}, "
                f"Media step: {user_data['media_step']}, "
                f"Sheet: {user_data['sheet_name']}, "
                f"Media count: {sum(len(urls) for urls in user_data['media_urls'].values())}"
            )
        else:
            logger.debug(f"User {chat_id} has no state data")

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old user sessions"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        expired_users = []
        for chat_id, user_data in self.user_states.items():
            if current_time - user_data['last_activity'] > max_age_seconds:
                expired_users.append(chat_id)
        
        for chat_id in expired_users:
            del self.user_states[chat_id]
            logger.info(f"Cleaned up expired session for user {chat_id}")
        
        if expired_users:
            logger.info(f"Cleaned up {len(expired_users)} expired sessions")

    def get_active_users_count(self) -> int:
        """Get count of active users"""
        return len(self.user_states)

    def get_user_stats(self) -> Dict:
        """Get user statistics"""
        stats = {
            'total_users': len(self.user_states),
            'states': {},
            'kendala_types': {}
        }
        
        for user_data in self.user_states.values():
            # Count states
            state = user_data['state'].value
            stats['states'][state] = stats['states'].get(state, 0) + 1
            
            # Count kendala types
            if user_data['kendala_type']:
                kendala = user_data['kendala_type'].value
                stats['kendala_types'][kendala] = stats['kendala_types'].get(kendala, 0) + 1
        
        return stats


# Global instance
user_manager = UserStateManager()