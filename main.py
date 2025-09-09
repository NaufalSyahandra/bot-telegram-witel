import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import Config
from handlers.bot_handlers import BotHandlers
from user_state_manager import user_manager

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Enhanced Telegram Bot with modular handler architecture"""

    def __init__(self):
        self.app = None
        self.bot_handlers = BotHandlers()
        self._setup_application()
        self._register_handlers()

    def _setup_application(self):
        """Setup Telegram application with validation"""
        Config.validate_config()
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        logger.info("Telegram application initialized with modular handler architecture")

    def _register_handlers(self):
        """Register all bot handlers in proper order"""

        # Command handlers
        command_handlers = [
            ("start", self.bot_handlers.start_command),
            ("help", self.bot_handlers.help_command),
            ("stats", self.bot_handlers.stats_command),
            ("cleanup", self.bot_handlers.cleanup_command),
        ]

        for command, handler in command_handlers:
            self.app.add_handler(CommandHandler(command, handler))

        # Callback query handler (must be before menu handlers)
        self.app.add_handler(self.bot_handlers.get_callback_handler())

        # Menu button patterns
        menu_pattern = self._build_menu_pattern()
        self.app.add_handler(MessageHandler(filters.Regex(menu_pattern), self.bot_handlers.menu_handler))

        # Media handlers
        self.app.add_handler(MessageHandler(filters.PHOTO, self.bot_handlers.handle_media))
        self.app.add_handler(MessageHandler(filters.VIDEO, self.bot_handlers.handle_media))

        # Text input handler (excludes commands and menu buttons)
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(menu_pattern),
            self.bot_handlers.handle_input
        ))

        # Fallback handler (must be last)
        self.app.add_handler(MessageHandler(filters.ALL, self.bot_handlers.fallback_handler))

        # Error handler
        self.app.add_error_handler(self.bot_handlers.error_handler)

        logger.info("All handlers registered successfully with modular architecture")

    def _build_menu_pattern(self):
        """Build regex pattern for menu buttons"""
        menu_buttons = [
            # Main menu
            "🔧 Kendala Teknik", "👤 Kendala Pelanggan", "❓ Kendala Lainnya", "🆘 Bantuan",

            # Teknik submenu
            "📶 Tidak ada Jaringan \\(TAJ\\)", "🏗️ Tidak ada Tiang \\(TAT\\)", "🔌 ODP Full",

            # TAT submenu
            "✅ TAT Sudah ACC", "❌ TAT Belum ACC",

            # Pelanggan submenu
            "😤 Pelanggan Manja", "❌ Pelanggan Cancel", "🔄 Cabut Pasang",

            # Admin menu
            "📋 Lihat Pendaftar", "👥 Lihat Admin", "➕ Tambah Admin",
            "🗂️ Kelola User", "➖ Hapus Admin", "🗑️ Hapus User",

            # Navigation
            "🏠 Menu Utama", "✅ Selesai"
        ]

        return "^(" + "|".join(menu_buttons) + ")$"

    async def _initialize_bot_data(self):
        """Initialize bot data from spreadsheet on startup"""
        try:
            logger.info("Initializing bot data from spreadsheet...")
            await user_manager.initialize_from_spreadsheet()
            logger.info("Bot data initialization completed successfully")
        except Exception as e:
            logger.error(f"Failed to initialize bot data: {e}")
            logger.warning("Bot will continue with empty user data - users will need to register")

    async def _post_init(self, application):
        """Post-initialization hook called by Application"""
        await self._initialize_bot_data()

    def run(self):
        """Start the bot with enhanced logging and error handling"""
        try:

            # Add post_init callback
            self.app.post_init = self._post_init

            logger.info("Starting bot polling...")
            self.app.run_polling(allowed_updates=Update.ALL_TYPES)

        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise


def main():
    """Main entry point with enhanced error handling"""
    try:
        bot = TelegramBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Bot crashed with critical error: {e}")
        logger.exception("Full traceback:")
        raise


if __name__ == "__main__":
    main()