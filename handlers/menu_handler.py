from .base_handler import BaseHandler, UserState, Messages, MenuKeyboards, Update, ContextTypes, user_manager, logger
from .admin_handler import AdminHandler
from constants import KendalaType
from utils.data_processor import DataProcessor


class MenuHandler(BaseHandler):
    """Handle menu navigation and user interactions"""

    def __init__(self):
        self.data_processor = DataProcessor()
        self.admin_handler = AdminHandler()

    async def menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button selections"""
        text = update.message.text
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)

        logger.debug(f"Menu handler: User {chat_id}, Button: {text}, State: {current_state.value}")

        # Handle admin and owner menu options
        admin_owner_buttons = [
            "📋 Lihat Pendaftar", "👥 Lihat Admin", "➕ Tambah Admin",
            "🗂️ Kelola User", "➖ Hapus Admin", "🗑️ Hapus User"
        ]
        if text in admin_owner_buttons:
            return await self.admin_handler.handle_admin_buttons(update, context, text)

        # Check authorization for regular menu items
        if not self._is_user_authorized(chat_id):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        # Define menu action mapping
        menu_actions = {
            # Main menu
            "🔧 Kendala Teknik": lambda: self._handle_teknik_menu(update, chat_id),
            "👤 Kendala Pelanggan": lambda: self._handle_pelanggan_menu(update, chat_id),
            "❓ Kendala Lainnya": lambda: self._handle_kendala_lainnya(update, chat_id),
            "🆘 Bantuan": lambda: self._handle_bantuan(update, chat_id),

            # Teknik submenu
            "📶 Tidak ada Jaringan (TAJ)": lambda: self._handle_kendala_input(update, chat_id, KendalaType.TAJ),
            "🏗️ Tidak ada Tiang (TAT)": lambda: self._handle_tat_submenu(update, chat_id),
            "🔌 ODP Full": lambda: self._handle_kendala_input(update, chat_id, KendalaType.ODP_FULL),

            # TAT submenu
            "✅ TAT Sudah ACC": lambda: self._handle_kendala_input(update, chat_id, KendalaType.TAT_SUDAH_ACC),
            "❌ TAT Belum ACC": lambda: self._handle_kendala_input(update, chat_id, KendalaType.TAT_BELUM_ACC),

            # Pelanggan submenu
            "😤 Pelanggan Manja": lambda: self._handle_kendala_input(update, chat_id, KendalaType.PELANGGAN_MANJA),
            "❌ Pelanggan Cancel": lambda: self._handle_kendala_input(update, chat_id, KendalaType.PELANGGAN_CANCEL),
            "🔄 Cabut Pasang": lambda: self._handle_kendala_input(update, chat_id, KendalaType.CABUT_PASANG),

            # Navigation
            "🏠 Menu Utama": lambda: self._handle_main_menu(update, chat_id),
            "✅ Selesai": lambda: self._handle_finish_media(update, context, chat_id),
        }

        action = menu_actions.get(text)
        if action:
            await action()

    # Menu action handlers
    async def _handle_teknik_menu(self, update, chat_id):
        user_manager.set_user_state(chat_id, UserState.TEKNIK_SUBMENU)
        await update.message.reply_text(Messages.TEKNIK_SUBMENU, reply_markup=MenuKeyboards.teknik_menu())

    async def _handle_pelanggan_menu(self, update, chat_id):
        user_manager.set_user_state(chat_id, UserState.PELANGGAN_SUBMENU)
        await update.message.reply_text(Messages.PELANGGAN_SUBMENU, reply_markup=MenuKeyboards.pelanggan_menu())

    async def _handle_kendala_lainnya(self, update, chat_id):
        user_manager.set_user_kendala_type(chat_id, KendalaType.LAINNYA)
        user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
        await update.message.reply_text(
            self.data_processor.get_input_format(KendalaType.LAINNYA),
            reply_markup=MenuKeyboards.back_menu()
        )

    async def _handle_bantuan(self, update, chat_id):
        user_manager.set_user_state(chat_id, UserState.IDLE)
        await update.message.reply_text(Messages.HELP_TEXT, reply_markup=self._get_appropriate_menu(chat_id))

    async def _handle_tat_submenu(self, update, chat_id):
        user_manager.set_user_state(chat_id, UserState.TAT_SUBMENU)
        await update.message.reply_text(Messages.TAT_SUBMENU, reply_markup=MenuKeyboards.tat_menu())

    async def _handle_kendala_input(self, update, chat_id, kendala_type):
        user_manager.set_user_kendala_type(chat_id, kendala_type)
        user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
        await update.message.reply_text(
            self.data_processor.get_input_format(kendala_type),
            reply_markup=MenuKeyboards.back_menu()
        )

    async def _handle_main_menu(self, update, chat_id):
        user_manager.set_user_state(chat_id, UserState.IDLE)
        user_manager.clear_user_data(chat_id)
        await update.message.reply_text("🏠 Kembali ke menu utama", reply_markup=self._get_appropriate_menu(chat_id))

    async def _handle_finish_media(self, update, context, chat_id):
        """Handle finish media button - delegated to media handler"""
        from .media_handler import MediaHandler
        media_handler = MediaHandler()
        await media_handler.handle_finish_media(update, context, chat_id)
