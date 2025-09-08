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
from user_state_manager import user_manager

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Main Telegram Bot class with enhanced user management and spreadsheet integration"""

    def __init__(self):
        self.app = None
        self._setup_application()
        self._register_handlers()

    def _setup_application(self):
        """Setup Telegram application"""
        # Validate configuration first
        Config.validate_config()
        
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        logger.info("Telegram application initialized with enhanced user management and spreadsheet integration")

    def _register_handlers(self):
        # Command handlers
        self.app.add_handler(CommandHandler("start", bot_handlers.start_command))
        self.app.add_handler(CommandHandler("help", bot_handlers.help_command))
        self.app.add_handler(CommandHandler("stats", bot_handlers.stats_command))
        self.app.add_handler(CommandHandler("cleanup", bot_handlers.cleanup_command))

        # Callback query handler for inline buttons (must be registered before menu handlers)
        self.app.add_handler(bot_handlers.get_callback_handler())

        menu_pattern = (
            "^(🔧 Kendala Teknik|👤 Kendala Pelanggan|❓ Kendala Lainnya|🆘 Bantuan|"
            "📶 Tidak ada Jaringan \\(TAJ\\)|🏗️ Tidak ada Tiang \\(TAT\\)|🔌 ODP Full|"
            "✅ TAT Sudah ACC|❌ TAT Belum ACC|"  # NEW: Added TAT submenu options
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

        logger.info("All handlers registered successfully with enhanced user management, re-registration support, and TAT submenu")

    async def _initialize_bot_data(self):
        """Initialize bot data from spreadsheet on startup"""
        try:
            logger.info("Initializing bot data from spreadsheet...")
            
            # Load user data from Teknisi sheet
            await user_manager.initialize_from_spreadsheet()
            
            logger.info("Bot data initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot data: {e}")
            logger.warning("Bot will continue with empty user data - users will need to register")

    async def _post_init(self, application):
        """Post-initialization hook called by Application"""
        await self._initialize_bot_data()

    def run(self):
        """Start the bot with data initialization"""
        try:
            logger.info("Starting Enhanced Telegram Bot with Spreadsheet Integration...")
            logger.info(f"Owner User ID: {Config.OWNER_USER_ID}")
            logger.info("Features enabled:")
            logger.info("- User registration with NIK validation (6-8 digits)")
            logger.info("- Admin and Owner role management")
            logger.info("- Data persistence in Google Sheets (Teknisi sheet)")
            logger.info("- Re-registration after rejection")
            logger.info("- Cross-notification for approvals/rejections")
            logger.info("- User removal by both owner and admin")
            logger.info("- Admin removal by owner")
            logger.info("- Inline approval/rejection buttons")
            logger.info("- Auto-load user data from spreadsheet on startup")
            
            # Add post_init callback for data initialization
            self.app.post_init = self._post_init
            
            logger.info("Starting bot polling...")
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