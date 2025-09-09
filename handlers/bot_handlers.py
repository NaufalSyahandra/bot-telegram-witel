import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from user_state_manager import user_manager

# Import all handler classes
from .auth_handler import AuthHandler
from .admin_handler import AdminHandler
from .callback_handler import CallbackHandler
from .menu_handler import MenuHandler
from .media_handler import MediaHandler
from .input_handler import InputHandler
from .utility_handler import UtilityHandler

logger = logging.getLogger(__name__)


class BotHandlers:
    """Main bot handlers orchestrator - delegates to specialized handlers"""

    def __init__(self):
        # Initialize all handler components
        self.auth_handler = AuthHandler()
        self.admin_handler = AdminHandler()
        self.callback_handler = CallbackHandler()
        self.menu = MenuHandler()
        self.media_handler = MediaHandler()
        self.input_handler = InputHandler()
        self.utility_handler = UtilityHandler()

        # Set owner user ID from config
        if hasattr(Config, 'OWNER_USER_ID'):
            user_manager.set_owner(Config.OWNER_USER_ID)
            logger.info(f"Bot initialized with owner ID: {Config.OWNER_USER_ID}")

    def get_callback_handler(self):
        """Get callback query handler for inline buttons"""
        return self.callback_handler.get_callback_handler()

    # Delegate methods to appropriate handlers
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.auth_handler.start_command(update, context)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.utility_handler.help_command(update, context)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.utility_handler.stats_command(update, context)

    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.utility_handler.cleanup_command(update, context)

    async def menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.menu.menu_handler(update, context)

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.media_handler.handle_media(update, context)

    async def handle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.input_handler.handle_input(update, context)

    async def fallback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.utility_handler.fallback_handler(update, context)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        return await self.utility_handler.error_handler(update, context)
