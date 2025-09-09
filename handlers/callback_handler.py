from .base_handler import BaseHandler, Update, ContextTypes, user_manager, logger, Messages, MenuKeyboards
from .notification_handler import NotificationHandler
from telegram.ext import CallbackQueryHandler


class CallbackHandler(BaseHandler):
    """Handle callback queries from inline buttons"""

    def __init__(self):
        self.notification_handler = NotificationHandler()

    def get_callback_handler(self):
        """Get callback query handler for inline buttons"""
        return CallbackQueryHandler(self.handle_callback_query)

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()

        chat_id = query.from_user.id

        if not (user_manager.is_owner(chat_id) or user_manager.is_admin(chat_id)):
            await query.edit_message_text("Anda tidak memiliki akses untuk fitur ini.")
            return

        data = query.data

        callback_handlers = {
            'approve_': self._handle_approval,
            'reject_': self._handle_rejection,
            'remove_user_': self._handle_user_removal,
            'remove_admin_': self._handle_admin_removal,
        }

        for prefix, handler in callback_handlers.items():
            if data.startswith(prefix):
                await handler(query, context, data)
                break

    async def _handle_approval(self, query, context, data):
        """Handle user approval"""
        nik = data.replace("approve_", "")
        result = await user_manager.approve_registration(nik, query.from_user.id)

        if result["success"]:
            user_data = result["user_data"]
            approved_user_id = user_data['user_id']
            username = user_data.get('username', 'N/A')

            # Notify approved user
            try:
                await context.bot.send_message(
                    chat_id=approved_user_id,
                    text=Messages.EMPLOYEE_APPROVED.format(nik=nik),
                    reply_markup=MenuKeyboards.main_menu()
                )
                logger.info(f"Notified approved user {approved_user_id} for NIK {nik}")
            except Exception as e:
                logger.error(f"Failed to notify approved user {approved_user_id}: {e}")

            # Handle cross-notifications
            await self.notification_handler.handle_approval_notifications(context, result)

            await query.edit_message_text(
                f"✅ Pendaftaran dengan NIK {nik} telah disetujui dan disimpan ke spreadsheet!\n"
                f"👤 User ID: {approved_user_id}\n"
                f"📧 Username: @{username}",
                reply_markup=None
            )
        else:
            reason = result.get("reason", "unknown")
            if reason == "not_found":
                await query.edit_message_text(f"❌ NIK {nik} tidak ditemukan dalam daftar pending.")
            else:
                await query.edit_message_text(f"❌ Gagal menyetujui pendaftaran NIK {nik}.")

    async def _handle_rejection(self, query, context, data):
        """Handle user rejection"""
        nik = data.replace("reject_", "")
        result = user_manager.reject_registration(nik, query.from_user.id)

        if result["success"]:
            user_data = result["user_data"]
            rejected_user_id = user_data['user_id']
            username = user_data.get('username', 'N/A')

            # Notify rejected user
            try:
                await context.bot.send_message(
                    chat_id=rejected_user_id,
                    text=Messages.EMPLOYEE_REJECTED.format(nik=nik)
                )
                logger.info(f"Notified rejected user {rejected_user_id} for NIK {nik}")
            except Exception as e:
                logger.error(f"Failed to notify rejected user {rejected_user_id}: {e}")

            # Handle cross-notifications
            await self.notification_handler.handle_rejection_notifications(context, result)

            await query.edit_message_text(
                f"❌ Pendaftaran dengan NIK {nik} telah ditolak!\n"
                f"👤 User ID: {rejected_user_id}\n"
                f"📧 Username: @{username}",
                reply_markup=None
            )
        else:
            reason = result.get("reason", "unknown")
            if reason == "not_found":
                await query.edit_message_text(f"❌ NIK {nik} tidak ditemukan dalam daftar pending.")
            else:
                await query.edit_message_text(f"❌ Gagal menolak pendaftaran NIK {nik}.")

    async def _handle_user_removal(self, query, context, data):
        """Handle user removal"""
        chat_id = query.from_user.id

        if not (user_manager.is_owner(chat_id) or user_manager.is_admin(chat_id)):
            await query.edit_message_text("Anda tidak memiliki akses untuk menghapus user.")
            return

        nik = data.replace("remove_user_", "")
        user_data = user_manager.get_user_by_nik(nik)

        if not user_data:
            await query.edit_message_text(f"❌ User dengan NIK {nik} tidak ditemukan.")
            return

        removed_user_id = user_data.get('user_id')
        username = user_data.get('username', 'N/A')

        success = await user_manager.remove_user(nik)

        if success:
            # Notify removed user
            if removed_user_id:
                try:
                    await context.bot.send_message(
                        chat_id=removed_user_id,
                        text="⚠️ Akun Anda telah dihapus dari sistem.\n\nUntuk menggunakan bot kembali, silakan daftar ulang dengan mengirim /start"
                    )
                    logger.info(f"Notified removed user {removed_user_id}")
                except Exception as e:
                    logger.error(f"Failed to notify removed user {removed_user_id}: {e}")

            # Handle cross-notifications for user removal
            await self.notification_handler.handle_user_removal_notifications(
                context, nik, username, removed_user_id, chat_id
            )

            await query.edit_message_text(f"✅ User dengan NIK {nik} telah dihapus!")
        else:
            await query.edit_message_text(f"❌ Gagal menghapus user dengan NIK {nik}.")

    async def _handle_admin_removal(self, query, context, data):
        """Handle admin removal (owner only)"""
        if not user_manager.is_owner(query.from_user.id):
            await query.edit_message_text("Hanya owner yang dapat menghapus admin.")
            return

        nik = data.replace("remove_admin_", "")
        user_data = user_manager.get_user_by_nik(nik)
        admin_user_id = user_data.get('user_id') if user_data else None
        admin_username = user_data.get('username', 'N/A') if user_data else 'N/A'

        success = await user_manager.remove_admin(nik)

        if success:
            # Notify demoted admin
            if admin_user_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_user_id,
                        text="⚠️ Status admin Anda telah dicabut.\n\nAnda masih dapat menggunakan bot sebagai employee biasa.",
                        reply_markup=MenuKeyboards.main_menu()
                    )
                    logger.info(f"Notified demoted admin {admin_user_id}")
                except Exception as e:
                    logger.error(f"Failed to notify demoted admin {admin_user_id}: {e}")

            # Notify other admins
            owner_nik = user_manager.get_user_nik(query.from_user.id) or "owner"
            await self.notification_handler.notify_other_admins_about_admin_removal(
                context, nik, admin_username, owner_nik
            )

            await query.edit_message_text(f"✅ Admin dengan NIK {nik} telah dihapus!")
        else:
            await query.edit_message_text(f"❌ Gagal menghapus admin dengan NIK {nik}.")
