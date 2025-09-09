from .base_handler import BaseHandler, Messages, user_manager, logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class NotificationHandler(BaseHandler):
    """Handle all notification logic"""

    async def _notify_admins_new_registration(self, context, nik: str, user_id: int, username: str):
        """Notify all admins about new registration"""
        message = Messages.ADMIN_APPROVAL_NOTIFICATION.format(
            nik=nik, user_id=user_id, username=username or "N/A"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Setujui", callback_data=f"approve_{nik}"),
                InlineKeyboardButton("❌ Tolak", callback_data=f"reject_{nik}")
            ]
        ])

        # Notify owner
        if user_manager.owner_user_id:
            try:
                await context.bot.send_message(
                    chat_id=user_manager.owner_user_id, text=message, reply_markup=keyboard
                )
                logger.info(f"Notified owner about new registration: NIK {nik}")
            except Exception as e:
                logger.error(f"Failed to notify owner: {e}")

        # Notify admins
        for nik_admin in user_manager.admins:
            admin_data = user_manager.registered_users.get(nik_admin)
            if admin_data:
                admin_user_id = admin_data.get('user_id')
                if admin_user_id and admin_user_id != user_manager.owner_user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_user_id, text=message, reply_markup=keyboard
                        )
                        logger.info(f"Notified admin {nik_admin} about new registration: NIK {nik}")
                    except Exception as e:
                        logger.error(f"Failed to notify admin {nik_admin}: {e}")

    async def handle_approval_notifications(self, context, result):
        """Handle cross-notifications for approval"""
        approver_user_id = result["approver_user_id"]
        nik = result["user_data"]["nik"]  # Assuming this is available in result
        user_id = result["user_data"]["user_id"]
        username = result["user_data"].get("username", "N/A")
        approver_nik = result["approver_nik"]

        if user_manager.is_owner(approver_user_id):
            await self._notify_admins_about_owner_action(
                context, nik, user_id, username, "disetujui", approver_nik
            )
        else:
            await self._notify_owner_about_admin_action(
                context, nik, user_id, username, "disetujui", "admin", approver_nik
            )

    async def handle_rejection_notifications(self, context, result):
        """Handle cross-notifications for rejection"""
        rejector_user_id = result["rejector_user_id"]
        nik = result["user_data"]["nik"]  # Assuming this is available in result
        user_id = result["user_data"]["user_id"]
        username = result["user_data"].get("username", "N/A")
        rejector_nik = result["rejector_nik"]

        if user_manager.is_owner(rejector_user_id):
            await self._notify_admins_about_owner_action(
                context, nik, user_id, username, "ditolak", rejector_nik
            )
        else:
            await self._notify_owner_about_admin_action(
                context, nik, user_id, username, "ditolak", "admin", rejector_nik
            )

    async def handle_user_removal_notifications(self, context, nik: str, username: str, removed_user_id: int,
                                                remover_user_id: int):
        """Handle cross-notifications for user removal"""
        remover_role = "owner" if user_manager.is_owner(remover_user_id) else "admin"
        remover_nik = user_manager.get_user_nik(remover_user_id) or "owner"

        if user_manager.is_owner(remover_user_id):
            await self._notify_admins_about_owner_removal(context, nik, username, removed_user_id, remover_nik)
        else:
            await self._notify_owner_about_admin_removal(context, nik, username, removed_user_id, remover_role,
                                                         remover_nik)

    # Private notification methods...
    async def _notify_owner_about_admin_action(self, context, nik: str, user_id: int, username: str, action: str,
                                               admin_role: str, admin_nik: str):
        """Notify owner about admin actions"""
        if not user_manager.owner_user_id:
            return

        try:
            action_emoji = "✅" if action == "disetujui" else "❌"
            message = (f"{action_emoji} **Notifikasi Aksi Admin**\n\n"
                       f"📋 Pendaftaran dengan NIK `{nik}` telah **{action}** oleh admin.\n\n"
                       f"👤 **Detail User:**\n• NIK: `{nik}`\n• User ID: `{user_id}`\n• Username: @{username}\n\n"
                       f"🔧 **Admin yang melakukan aksi:**\n• Role: {admin_role}\n• NIK: {admin_nik}")

            await context.bot.send_message(
                chat_id=user_manager.owner_user_id, text=message, parse_mode='Markdown'
            )
            logger.info(f"Notified owner about {action} action by admin {admin_nik} for NIK {nik}")
        except Exception as e:
            logger.error(f"Failed to notify owner about admin action: {e}")

    async def _notify_admins_about_owner_action(self, context, nik: str, user_id: int, username: str, action: str,
                                                owner_nik: str):
        """Notify all admins about owner actions"""
        action_emoji = "✅" if action == "disetujui" else "❌"
        message = (f"{action_emoji} **Notifikasi Aksi Owner**\n\n"
                   f"📋 Pendaftaran dengan NIK `{nik}` telah **{action}** oleh owner.\n\n"
                   f"👤 **Detail User:**\n• NIK: `{nik}`\n• User ID: `{user_id}`\n• Username: @{username}\n\n"
                   f"👑 **Owner:** {owner_nik}")

        for admin_nik in user_manager.admins:
            admin_data = user_manager.registered_users.get(admin_nik)
            if admin_data:
                admin_user_id = admin_data.get('user_id')
                if admin_user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_user_id, text=message, parse_mode='Markdown'
                        )
                        logger.info(f"Notified admin {admin_nik} about owner {action} action for NIK {nik}")
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin_nik} about owner action: {e}")
