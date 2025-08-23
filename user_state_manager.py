import time
import logging
from collections import defaultdict
from typing import Dict, List, Optional
from constants import UserState, KendalaType

logger = logging.getLogger(__name__)


class UserStateManager:
    """Manages user states and session data"""

    def __init__(self):
        # User state management (in production, use database)
        self._user_state: Dict[int, UserState] = {}
        self._user_last_request: Dict[int, float] = defaultdict(float)
        self._user_kendala_type: Dict[int, KendalaType] = {}
        self._user_last_row: Dict[int, int] = {}
        self._user_media_urls: Dict[int, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        self._user_media_count: Dict[int, int] = defaultdict(int)
        self._user_parsed_data: Dict[int, Dict[str, str]] = {}
        self._user_media_step: Dict[int, int] = defaultdict(int)

    def get_user_state(self, chat_id: int) -> UserState:
        """Get current user state"""
        return self._user_state.get(chat_id, UserState.IDLE)

    def set_user_state(self, chat_id: int, state: UserState):
        """Set user state"""
        self._user_state[chat_id] = state
        logger.info(f"User {chat_id} state changed to: {state.value}")

    def get_user_kendala_type(self, chat_id: int) -> Optional[KendalaType]:
        """Get user's selected kendala type"""
        return self._user_kendala_type.get(chat_id)

    def set_user_kendala_type(self, chat_id: int, kendala_type: KendalaType):
        """Set user's kendala type"""
        self._user_kendala_type[chat_id] = kendala_type
        logger.info(f"User {chat_id} kendala type set to: {kendala_type.value}")

    def get_user_last_row(self, chat_id: int) -> int:
        """Get user's last spreadsheet row"""
        return self._user_last_row.get(chat_id, 0)

    def set_user_last_row(self, chat_id: int, row_number: int):
        """Set user's last spreadsheet row"""
        self._user_last_row[chat_id] = row_number

    def get_user_media_urls(self, chat_id: int) -> Dict[str, List[str]]:
        """Get user's uploaded media URLs"""
        return self._user_media_urls.get(chat_id, defaultdict(list))

    def add_user_media_url(self, chat_id: int, media_type: str, url: str):
        """Add media URL for user"""
        self._user_media_urls[chat_id][media_type].append(url)
        self._user_media_count[chat_id] += 1
        logger.info(f"Media URL added for user {chat_id}: {media_type}")

    def get_user_media_step(self, chat_id: int) -> int:
        """Get current media step for user"""
        return self._user_media_step.get(chat_id, 0)

    def set_user_media_step(self, chat_id: int, step: int):
        """Set current media step for user"""
        self._user_media_step[chat_id] = step

    def increment_user_media_step(self, chat_id: int):
        """Increment user media step"""
        old_step = self._user_media_step.get(chat_id, 0)
        self._user_media_step[chat_id] = old_step + 1
        logger.info(f"Media step incremented for user {chat_id}: {old_step} -> {self._user_media_step[chat_id]}")

    def get_user_media_count(self, chat_id: int) -> int:
        """Get total media count for user"""
        return self._user_media_count.get(chat_id, 0)

    def get_user_parsed_data(self, chat_id: int) -> Dict[str, str]:
        """Get user's parsed input data"""
        return self._user_parsed_data.get(chat_id, {})

    def set_user_parsed_data(self, chat_id: int, data: Dict[str, str]):
        """Set user's parsed input data"""
        self._user_parsed_data[chat_id] = data

    def clear_user_data(self, chat_id: int):
        """Clear all user data for fresh start"""
        logger.info(f"Clearing user data for chat_id {chat_id}")
        self._user_kendala_type.pop(chat_id, None)
        self._user_last_row.pop(chat_id, None)
        self._user_media_urls.pop(chat_id, None)
        self._user_media_count.pop(chat_id, None)
        self._user_parsed_data.pop(chat_id, None)
        self._user_media_step.pop(chat_id, None)

    def check_rate_limit(self, chat_id: int, rate_limit_seconds: int = 2) -> bool:
        """Check if user is within rate limit"""
        now = time.time()
        if now - self._user_last_request[chat_id] < rate_limit_seconds:
            return False
        self._user_last_request[chat_id] = now
        return True

    def debug_user_state(self, chat_id: int):
        """Debug function to log user state"""
        logger.info(f"DEBUG - User {chat_id} state:")
        logger.info(f"  - State: {self.get_user_state(chat_id)}")
        logger.info(f"  - Kendala type: {self.get_user_kendala_type(chat_id)}")
        logger.info(f"  - Media step: {self.get_user_media_step(chat_id)}")
        logger.info(f"  - Media count: {self.get_user_media_count(chat_id)}")
        logger.info(f"  - Media URLs: {self.get_user_media_urls(chat_id)}")


# Global instance - in production, consider using dependency injection
user_manager = UserStateManager()