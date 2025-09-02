import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import Config
from handlers.handlers import bot_handlers

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Main Telegram Bot class with enhanced user management and re-registration support"""

    def __init__(self):
        self.app = None
        self._setup_application()
        self._register_handlers()

    def _setup_application(self):
        """Setup Telegram application"""
        # Validate configuration first
        Config.validate_config()
        
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        logger.info("Telegram application initialized with enhanced user management")

    def _register_handlers(self):
        """Register all bot handlers with enhanced user management and re-registration support"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", bot_handlers.start_command))
        self.app.add_handler(CommandHandler("help", bot_handlers.help_command))
        self.app.add_handler(CommandHandler("stats", bot_handlers.stats_command))
        self.app.add_handler(CommandHandler("cleanup", bot_handlers.cleanup_command))

        # Callback query handler for inline buttons (must be registered before menu handlers)
        self.app.add_handler(bot_handlers.get_callback_handler())

        # Enhanced menu handlers with user management options (updated pattern)
        menu_pattern = (
            "^(🔧 Kendala Teknik|👤 Kendala Pelanggan|❓ Kendala Lainnya|🆘 Bantuan|"
            "📶 Tidak ada Jaringan \\(TAJ\\)|🏗️ Tidak ada Tiang \\(TAT\\)|🔌 ODP Full|"
            "😤 Pelanggan Manja|❌ Pelanggan Cancel|🔄 Cabut Pasang|"
            "📋 Lihat Pendaftar|👥 Lihat Admin|➕ Tambah Admin|🗂️ Kelola User|➖ Hapus Admin|🗑️ Hapus User|"
            "🏠 Menu Utama|✅ Selesai)$"
        )
        self.app.add_handler(MessageHandler(filters.Regex(menu_pattern), bot_handlers.menu_handler))

        # Media handlers (photo and video)
        self.app.add_handler(MessageHandler(filters.PHOTO, bot_handlers.handle_media))
        self.app.add_handler(MessageHandler(filters.VIDEO, bot_handlers.handle_media))

        # Input handler (text that's not command or menu button) - Enhanced to handle re-registration
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(menu_pattern),
            bot_handlers.handle_input
        ))

        # Fallback handler (catch-all, must be last)
        self.app.add_handler(MessageHandler(filters.ALL, bot_handlers.fallback_handler))

        # Error handler
        self.app.add_error_handler(bot_handlers.error_handler)

        logger.info("All handlers registered successfully with enhanced user management and re-registration support")

    def run(self):
        """Start the bot"""
        try:
            logger.info("Starting Enhanced Telegram Bot...")
            logger.info(f"Owner User ID: {Config.OWNER_USER_ID}")
            logger.info("Features enabled:")
            logger.info("- User registration with NIK validation (6-8 digits)")
            logger.info("- Admin and Owner role management")
            logger.info("- Re-registration after rejection (no processed_registrations tracking)")
            logger.info("- Cross-notification for approvals/rejections to owner")
            logger.info("- User removal by both owner and admin")
            logger.info("- Admin removal by owner")
            logger.info("- Inline approval/rejection buttons")
            logger.info("- Owner notifications when admin approves/rejects/removes users")
            self.app.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise


def main():
    """Main entry point"""
    try:
        bot = TelegramBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise


if __name__ == "__main__":
    main()