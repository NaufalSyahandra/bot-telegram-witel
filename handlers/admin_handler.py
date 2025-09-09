from .base_handler import BaseHandler, user_manager, logger, ContextTypes, Update, UserState, Messages, MenuKeyboards
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class AdminHandler(BaseHandler):
    """Handle admin-specific operations"""

    async def handle_admin_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle admin menu buttons"""
        chat_id = update.effective_chat.id

        if not (user_manager.is_owner(chat_id) or user_manager.is_admin(chat_id)):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return True

        button_handlers = {
            "📋 Lihat Pendaftar": self._show_pending_registrations,
            "👥 Lihat Admin": self._show_admin_list,
            "➕ Tambah Admin": self._handle_add_admin,
            "🗂️ Kelola User": self._show_user_management,
            "➖ Hapus Admin": self._show_admin_removal_options,
            "🗑️ Hapus User": self._show_user_removal_options,
        }

        handler = button_handlers.get(text)
        if handler:
            await handler(update, context)

        return True

    async def handle_admin_nik_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin NIK input from owner"""
        chat_id = update.effective_chat.id
        text = update.message.text.strip()

        if user_manager.get_user_state(chat_id) != UserState.WAITING_ADMIN_NIK or not user_manager.is_owner(chat_id):
            return False

        if not text.isdigit() or not (6 <= len(text) <= 8):
            await update.message.reply_text(Messages.INVALID_NIK)
            return True

        success = await user_manager.add_admin(text)
        user_manager.set_user_state(chat_id, UserState.IDLE)

        if success:
            await update.message.reply_text(
                Messages.ADMIN_ADDED.format(nik=text) + "\n\n📊 Data admin telah disinkronkan ke spreadsheet.",
                reply_markup=MenuKeyboards.owner_menu()
            )

            # Notify new admin
            user_data = user_manager.get_user_by_nik(text)
            if user_data and user_data.get('user_id'):
                try:
                    await context.bot.send_message(
                        chat_id=user_data['user_id'],
                        text="🔧 Anda telah ditunjuk sebagai admin!\n\nSekarang Anda memiliki akses ke fitur admin.",
                        reply_markup=MenuKeyboards.admin_menu()
                    )
                    logger.info(f"Notified new admin {text} about role assignment")
                except Exception as e:
                    logger.error(f"Failed to notify new admin {text}: {e}")
        else:
            await update.message.reply_text(Messages.ADMIN_ADD_ERROR, reply_markup=MenuKeyboards.owner_menu())

        return True

    # Private helper methods
    async def _show_pending_registrations(self, update, context=None):
        """Show pending registrations with inline buttons"""
        pending = user_manager.get_pending_registrations()
        if not pending:
            await update.message.reply_text("Tidak ada pendaftar yang menunggu approval.")
        else:
            for i, registration in enumerate(pending):
                nik = registration['nik']
                username = registration.get('username', 'N/A')
                user_id = registration['user_id']

                message = (f"📋 **Pendaftaran #{i + 1}**\n\n"
                           f"NIK: `{nik}`\n"
                           f"User ID: `{user_id}`\n"
                           f"Username: @{username}\n"
                           f"Waktu: {self._format_timestamp(registration['timestamp'])}")

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Setujui", callback_data=f"approve_{nik}"),
                        InlineKeyboardButton("❌ Tolak", callback_data=f"reject_{nik}")
                    ]
                ])

                await update.message.reply_text(message, parse_mode='Markdown', reply_markup=keyboard)

    async def _show_admin_list(self, update, context=None):
        """Show admin list"""
        if not user_manager.is_owner(update.effective_chat.id):
            return

        admin_list = user_manager.get_admin_list()
        if not admin_list:
            await update.message.reply_text("Belum ada admin yang terdaftar.")
        else:
            message = "👥 **Daftar Admin:**\n\n"
            for i, admin in enumerate(admin_list, 1):
                message += f"{i}. NIK: `{admin['nik']}`\n"
                message += f"   Username: @{admin.get('username', 'N/A')}\n"
                message += f"   User ID: `{admin.get('user_id', 'N/A')}`\n\n"

            await update.message.reply_text(message, parse_mode='Markdown')

    async def _handle_add_admin(self, update, context=None):
        """Handle add admin button"""
        if not user_manager.is_owner(update.effective_chat.id):
            return

        user_manager.set_user_state(update.effective_chat.id, UserState.WAITING_ADMIN_NIK)
        await update.message.reply_text(Messages.ADD_ADMIN_REQUEST)

    async def _show_user_management(self, update, context=None):
        """Show user management options"""
        if not user_manager.is_owner(update.effective_chat.id):
            return

        all_users = user_manager.get_all_users_list()
        if not all_users:
            await update.message.reply_text("Belum ada user yang terdaftar.")
            return

        message = "🗂️ **Kelola User (Daftar Semua User):**\n\n"

        for i, user in enumerate(all_users[:10], 1):
            role_emoji = "👑" if user['role'] == "owner" else "🔧" if user['role'] == "admin" else "👤"
            message += f"{i}. {role_emoji} NIK: `{user['nik']}`\n"
            message += f"   Username: @{user.get('username', 'N/A')}\n"
            message += f"   Role: {user['role'].title()}\n"
            message += f"   Status: {user['status'].title()}\n\n"

        if len(all_users) > 10:
            message += f"... dan {len(all_users) - 10} user lainnya\n\n"

        message += "💡 Gunakan menu untuk mengelola admin dan user."
        await update.message.reply_text(message, parse_mode='Markdown')

    async def _show_admin_removal_options(self, update, context=None):
        """Show admin removal options"""
        if not user_manager.is_owner(update.effective_chat.id):
            return

        admin_list = user_manager.get_admin_list()
        if not admin_list:
            await update.message.reply_text("Tidak ada admin yang dapat dihapus.")
            return

        buttons = []
        for admin in admin_list[:5]:
            nik = admin['nik']
            username = admin.get('username', nik)
            buttons.append([
                InlineKeyboardButton(f"❌ Hapus {username} ({nik})", callback_data=f"remove_admin_{nik}")
            ])

        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(
            "➖ **Hapus Admin**\n\nPilih admin yang akan dihapus:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )

    async def _show_user_removal_options(self, update, context=None):
        """Show user removal options"""
        all_users = user_manager.get_all_users_list()
        if not all_users:
            await update.message.reply_text("Tidak ada user yang dapat dihapus.")
            return

        buttons = []
        for user in all_users[:10]:
            nik = user['nik']
            username = user.get('username', nik)
            role_emoji = "👑" if user['role'] == "owner" else "🔧" if user['role'] == "admin" else "👤"

            if user['role'] != "owner":
                buttons.append([
                    InlineKeyboardButton(f"🗑️ {role_emoji} {username} ({nik})", callback_data=f"remove_user_{nik}")
                ])

        if not buttons:
            await update.message.reply_text("Tidak ada user yang dapat dihapus.")
            return

        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(
            "🗑️ **Hapus User**\n\nPilih user yang akan dihapus:\n\n"
            "⚠️ **Peringatan**: User yang dihapus akan kehilangan akses ke bot dan harus mendaftar ulang.",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
