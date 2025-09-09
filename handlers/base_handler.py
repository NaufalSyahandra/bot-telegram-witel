import logging
from abc import ABC, abstractmethod
from telegram import Update
from telegram.ext import ContextTypes
from user_state_manager import user_manager
from constants import UserState, Messages, MenuKeyboards

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """Base handler class with common functionality"""

    def _is_user_authorized(self, chat_id: int) -> bool:
        """Check if user is authorized to use bot features"""
        current_state = user_manager.get_user_state(chat_id)
        return current_state not in [UserState.UNREGISTERED, UserState.PENDING_APPROVAL, UserState.REJECTED]

    def _get_appropriate_menu(self, chat_id: int):
        """Get appropriate menu based on user role"""
        if user_manager.is_owner(chat_id):
            return MenuKeyboards.owner_menu()
        elif user_manager.is_admin(chat_id):
            return MenuKeyboards.admin_menu()
        else:
            return MenuKeyboards.main_menu()

    def _format_timestamp(self, timestamp: float) -> str:
        """Format timestamp for display"""
        import datetime
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")