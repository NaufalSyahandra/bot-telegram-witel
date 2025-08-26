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
    """Main Telegram Bot class"""

    def __init__(self):
        self.app = None
        self._setup_application()
        self._register_handlers()

    def _setup_application(self):
        """Setup Telegram application"""
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        logger.info("Telegram application initialized")

    def _register_handlers(self):
        """Register all bot handlers"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", bot_handlers.start_command))
        self.app.add_handler(CommandHandler("help", bot_handlers.help_command))

        # Menu handlers (specific buttons) - Updated to include pelanggan submenu
        menu_pattern = (
            "^(🔧 Kendala Teknik|👤 Kendala Pelanggan|❓ Kendala Lainnya|🆘 Bantuan|"
            "📶 Tidak ada Jaringan \\(TAJ\\)|🏗️ Tidak ada Tiang \\(TAT\\)|🔌 ODP Full|"
            "😤 Pelanggan Manja|❌ Pelanggan Cancel|🔄 Cabut Pasang|"
            "🏠 Menu Utama|✅ Selesai)$"
        )
        self.app.add_handler(MessageHandler(filters.Regex(menu_pattern), bot_handlers.menu_handler))

        # Media handlers (photo and video)
        self.app.add_handler(MessageHandler(filters.PHOTO, bot_handlers.handle_media))
        self.app.add_handler(MessageHandler(filters.VIDEO, bot_handlers.handle_media))

        # Input handler (text that's not command or menu button)
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(menu_pattern),
            bot_handlers.handle_input
        ))

        # Fallback handler (catch-all, must be last)
        self.app.add_handler(MessageHandler(filters.ALL, bot_handlers.fallback_handler))

        # Error handler
        self.app.add_error_handler(bot_handlers.error_handler)

        logger.info("All handlers registered successfully")

    def run(self):
        """Start the bot"""
        try:
            logger.info("Starting Telegram Bot...")
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