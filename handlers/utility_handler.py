from .base_handler import BaseHandler, UserState, Messages, MenuKeyboards, Update, ContextTypes, user_manager, logger
from utils.data_processor import DataProcessor


class UtilityHandler(BaseHandler):
    """Handle utility commands and fallback scenarios"""

    def __init__(self):
        self.data_processor = DataProcessor()

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        chat_id = update.effective_chat.id
        await update.message.reply_text(Messages.HELP_TEXT, reply_markup=self._get_appropriate_menu(chat_id))

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command for admins and owner"""
        chat_id = update.effective_chat.id

        if not (user_manager.is_owner(chat_id) or user_manager.is_admin(chat_id)):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        stats = user_manager.get_user_stats()

        message = "📊 **Statistik Bot:**\n\n"
        message += f"👥 Total User Aktif: {stats['total_active']}\n"
        message += f"✅ Total Terdaftar: {stats['total_registered']}\n"
        message += f"⏳ Menunggu Approval: {stats['pending_registrations']}\n"
        message += f"🔧 Total Admin: {stats['admins']}\n\n"

        if stats['states']:
            message += "📈 **Status User:**\n"
            for state, count in stats['states'].items():
                state_emoji = {
                    'idle': '💤', 'waiting_input': '✏️', 'waiting_media': '📸',
                    'pending_approval': '⏳', 'rejected': '❌', 'unregistered': '🚫'
                }.get(state, '📊')
                message += f"• {state_emoji} {state.replace('_', ' ').title()}: {count}\n"

        if stats['kendala_types']:
            message += "\n📋 **Jenis Kendala Aktif:**\n"
            for kendala, count in stats['kendala_types'].items():
                kendala_emoji = {
                    'taj': '📶', 'tat': '🏗️', 'odp_full': '🔌', 'pelanggan_manja': '😤',
                    'pelanggan_cancel': '❌', 'cabut_pasang': '🔄', 'lainnya': '❓'
                }.get(kendala, '📊')
                message += f"• {kendala_emoji} {kendala.upper()}: {count}\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cleanup command for owner"""
        chat_id = update.effective_chat.id

        if not user_manager.is_owner(chat_id):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        user_manager.cleanup_old_sessions(24)
        await update.message.reply_text(
            "🧹 Session cleanup completed!\n\nInactive sessions older than 24 hours have been removed.")

    async def fallback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unrecognized commands or messages"""
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)

        logger.debug(f"Fallback handler: User {chat_id}, State: {current_state.value}")

        # Handle unregistered/unauthorized users
        if current_state == UserState.UNREGISTERED:
            await update.message.reply_text(Messages.WELCOME_UNREGISTERED)
            return
        elif current_state == UserState.PENDING_APPROVAL:
            await update.message.reply_text(Messages.REGISTRATION_PENDING)
            return
        elif current_state == UserState.REJECTED:
            await update.message.reply_text(Messages.REGISTRATION_REJECTED_CAN_RETRY)
            return

        if not self._is_user_authorized(chat_id):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        # State-specific fallback messages
        fallback_handlers = {
            UserState.WAITING_INPUT: self._handle_input_fallback,
            UserState.WAITING_MEDIA: self._handle_media_fallback,
            UserState.WAITING_ADMIN_NIK: self._handle_admin_nik_fallback,
        }

        handler = fallback_handlers.get(current_state)
        if handler:
            await handler(update, chat_id)
        else:
            await update.message.reply_text(
                "❓ Perintah tidak dikenali. Gunakan menu di bawah atau ketik /start",
                reply_markup=self._get_appropriate_menu(chat_id)
            )

    async def _handle_input_fallback(self, update, chat_id):
        """Handle fallback for WAITING_INPUT state"""
        kendala_type = user_manager.get_user_kendala_type(chat_id)
        if kendala_type:
            await update.message.reply_text(
                "⚠️ Format data tidak dikenali.\n\n" + self.data_processor.get_input_format(kendala_type),
                reply_markup=MenuKeyboards.back_menu()
            )
        else:
            await update.message.reply_text(
                "❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start",
                reply_markup=self._get_appropriate_menu(chat_id)
            )

    async def _handle_media_fallback(self, update, chat_id):
        """Handle fallback for WAITING_MEDIA state"""
        kendala_type = user_manager.get_user_kendala_type(chat_id)
        if kendala_type:
            current_step = user_manager.get_user_media_step(chat_id)
            expected_media_info = self.data_processor.get_expected_media_info(kendala_type, current_step)
            if expected_media_info:
                field_name, media_type, description = expected_media_info
                media_name = "Foto" if media_type == "photo" else "Video"
                await update.message.reply_text(
                    f"📸 Kirim media dokumentasi sesuai urutan!\n\n"
                    f"🔸 **Yang diminta sekarang**: {media_name} - {description}",
                    reply_markup=MenuKeyboards.media_menu()
                )
            else:
                await update.message.reply_text(
                    "✅ Semua media sudah lengkap! Klik 'Selesai' untuk menyelesaikan.",
                    reply_markup=MenuKeyboards.media_menu()
                )
        else:
            await update.message.reply_text(
                "❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start",
                reply_markup=self._get_appropriate_menu(chat_id)
            )

    async def _handle_admin_nik_fallback(self, update, chat_id):
        """Handle fallback for WAITING_ADMIN_NIK state"""
        await update.message.reply_text(
            "📝 Silakan kirim NIK yang valid (6-8 digit) untuk admin baru:",
            reply_markup=MenuKeyboards.back_menu()
        )

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Enhanced error handler with user state debugging"""
        logger.error(f"Update {update} caused error {context.error}")

        # Try to get chat_id for debugging
        chat_id = None
        try:
            if hasattr(update, 'effective_chat') and update.effective_chat:
                chat_id = update.effective_chat.id
            elif hasattr(update, 'callback_query') and update.callback_query:
                chat_id = update.callback_query.from_user.id
            elif hasattr(update, 'message') and update.message:
                chat_id = update.message.chat_id
        except:
            pass

        if chat_id:
            user_manager.debug_user_state(chat_id)

    async def handle_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unknown commands"""
        chat_id = update.effective_chat.id
        command = update.message.text

        logger.warning(f"Unknown command from user {chat_id}: {command}")

        available_commands = [
            "• /start - Mulai ulang bot",
            "• /help - Bantuan"
        ]

        if user_manager.is_owner(chat_id) or user_manager.is_admin(chat_id):
            available_commands.extend([
                "• /stats - Lihat statistik",
                "• /cleanup - Cleanup sessions"
            ])

        await update.message.reply_text(
            f"❓ Command tidak dikenal: {command}\n\n"
            "Available commands:\n" + "\n".join(available_commands),
            reply_markup=self._get_appropriate_menu(chat_id)
        )

    def get_user_context_info(self, chat_id: int) -> dict:
        """Get comprehensive user context information for debugging"""
        role = user_manager.get_user_role(chat_id)
        kendala_type = user_manager.get_user_kendala_type(chat_id)

        return {
            'user_id': chat_id,
            'state': user_manager.get_user_state(chat_id).value,
            'nik': user_manager.get_user_nik(chat_id),
            'role': role.value if role else None,
            'is_owner': user_manager.is_owner(chat_id),
            'is_admin': user_manager.is_admin(chat_id),
            'is_registered': user_manager.is_user_registered(chat_id),
            'is_pending': user_manager.is_user_pending(chat_id),
            'kendala_type': kendala_type.value if kendala_type else None,
            'media_step': user_manager.get_user_media_step(chat_id),
            'media_count': user_manager.get_user_media_count(chat_id)
        }
