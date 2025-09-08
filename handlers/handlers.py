import logging
import gspread
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from config import Config
from constants import (
    UserState,
    KendalaType,
    UserRole,
    Messages,
    MenuKeyboards,
    MEDIA_FIELDS_WITH_TYPES,
    MEDIA_FIELDS,
    REQUIRED_FIELDS,
    SHEET_CONFIGS,
    get_sheet_config
)
from user_state_manager import user_manager
from services.sheets_service import sheets_service
from services.media_service import media_service
from utils.data_processor import DataProcessor

logger = logging.getLogger(__name__)


class BotHandlers:
    """Enhanced Bot message handlers class with complete user management"""

    def __init__(self):
        self.data_processor = DataProcessor()
        # Set owner user ID from config
        if hasattr(Config, 'OWNER_USER_ID'):
            user_manager.set_owner(Config.OWNER_USER_ID)
            logger.info(f"Bot initialized with owner ID: {Config.OWNER_USER_ID}")

    def get_callback_handler(self):
        """Get callback query handler for inline buttons"""
        return CallbackQueryHandler(self.handle_callback_query)

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks for approval/rejection and user management"""
        query = update.callback_query
        await query.answer()
        
        chat_id = query.from_user.id
        
        # Check if user has admin privileges
        if not (user_manager.is_owner(chat_id) or user_manager.is_admin(chat_id)):
            await query.edit_message_text("Anda tidak memiliki akses untuk fitur ini.")
            return

        data = query.data
        
        if data.startswith("approve_"):
            await self._handle_approval(query, context, data)
        elif data.startswith("reject_"):
            await self._handle_rejection(query, context, data)
        elif data.startswith("remove_user_"):
            await self._handle_user_removal(query, context, data)
        elif data.startswith("remove_admin_"):
            await self._handle_admin_removal(query, context, data)

    async def _handle_approval(self, query, context, data):
        """Handle user approval with bidirectional notifications and spreadsheet sync"""
        nik = data.replace("approve_", "")
        result = await user_manager.approve_registration(nik, query.from_user.id)  # Now async
        
        if result["success"]:
            user_data = result["user_data"]
            approved_user_id = user_data['user_id']
            username = user_data.get('username', 'N/A')
            approver_role = result["approver_role"]
            approver_nik = result["approver_nik"]
            approver_user_id = result["approver_user_id"]
            
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
            
            # Cross-notification logic
            if user_manager.is_owner(approver_user_id):
                # Owner approved - notify all admins
                await self._notify_admins_about_owner_action(
                    context, nik, approved_user_id, username, "disetujui", approver_nik
                )
            else:
                # Admin approved - notify owner
                await self._notify_owner_about_admin_action(
                    context, nik, approved_user_id, username, "disetujui", approver_role, approver_nik
                )
            
            await query.edit_message_text(
                f"✅ Pendaftaran dengan NIK {nik} telah disetujui dan disimpan ke spreadsheet!\n"
                f"👤 User ID: {approved_user_id}\n"
                f"📧 Username: @{username}",
                reply_markup=None
            )
        else:
            reason = result.get("reason", "unknown")
            if reason == "not_found":
                await query.edit_message_text(
                    f"❌ NIK {nik} tidak ditemukan dalam daftar pending.",
                    reply_markup=None
                )
            else:
                await query.edit_message_text(
                    f"❌ Gagal menyetujui pendaftaran NIK {nik}.",
                    reply_markup=None
                )

    async def _handle_rejection(self, query, context, data):
        """Handle user rejection with bidirectional notifications"""
        nik = data.replace("reject_", "")
        result = user_manager.reject_registration(nik, query.from_user.id)
        
        if result["success"]:
            user_data = result["user_data"]
            rejected_user_id = user_data['user_id']
            username = user_data.get('username', 'N/A')
            rejector_role = result["rejector_role"]
            rejector_nik = result["rejector_nik"]
            rejector_user_id = result["rejector_user_id"]
            
            # Notify rejected user
            try:
                await context.bot.send_message(
                    chat_id=rejected_user_id,
                    text=Messages.EMPLOYEE_REJECTED.format(nik=nik)
                )
                logger.info(f"Notified rejected user {rejected_user_id} for NIK {nik}")
            except Exception as e:
                logger.error(f"Failed to notify rejected user {rejected_user_id}: {e}")
            
            # Cross-notification logic
            if user_manager.is_owner(rejector_user_id):
                # Owner rejected - notify all admins
                await self._notify_admins_about_owner_action(
                    context, nik, rejected_user_id, username, "ditolak", rejector_nik
                )
            else:
                # Admin rejected - notify owner
                await self._notify_owner_about_admin_action(
                    context, nik, rejected_user_id, username, "ditolak", rejector_role, rejector_nik
                )
            
            await query.edit_message_text(
                f"❌ Pendaftaran dengan NIK {nik} telah ditolak!\n"
                f"👤 User ID: {rejected_user_id}\n"
                f"📧 Username: @{username}",
                reply_markup=None
            )
        else:
            reason = result.get("reason", "unknown")
            if reason == "not_found":
                await query.edit_message_text(
                    f"❌ NIK {nik} tidak ditemukan dalam daftar pending.",
                    reply_markup=None
                )
            else:
                await query.edit_message_text(
                    f"❌ Gagal menolak pendaftaran NIK {nik}.",
                    reply_markup=None
                )

    async def _notify_owner_about_admin_action(self, context, nik: str, user_id: int, username: str, action: str, admin_role: str, admin_nik: str):
        """Notify owner about admin approval/rejection actions"""
        if not user_manager.owner_user_id:
            return
            
        try:
            action_emoji = "✅" if action == "disetujui" else "❌"
            await context.bot.send_message(
                chat_id=user_manager.owner_user_id,
                text=f"{action_emoji} **Notifikasi Aksi Admin**\n\n"
                     f"📋 Pendaftaran dengan NIK `{nik}` telah **{action}** oleh admin.\n\n"
                     f"👤 **Detail User:**\n"
                     f"• NIK: `{nik}`\n"
                     f"• User ID: `{user_id}`\n"
                     f"• Username: @{username}\n\n"
                     f"🔧 **Admin yang melakukan aksi:**\n"
                     f"• Role: {admin_role}\n"
                     f"• NIK: {admin_nik}",
                parse_mode='Markdown'
            )
            logger.info(f"Notified owner about {action} action by admin {admin_nik} for NIK {nik}")
        except Exception as e:
            logger.error(f"Failed to notify owner about admin action: {e}")

    async def _notify_admins_about_owner_action(self, context, nik: str, user_id: int, username: str, action: str, owner_nik: str):
        """Notify all admins about owner approval/rejection actions"""
        action_emoji = "✅" if action == "disetujui" else "❌"
        message = (f"{action_emoji} **Notifikasi Aksi Owner**\n\n"
                  f"📋 Pendaftaran dengan NIK `{nik}` telah **{action}** oleh owner.\n\n"
                  f"👤 **Detail User:**\n"
                  f"• NIK: `{nik}`\n"
                  f"• User ID: `{user_id}`\n"
                  f"• Username: @{username}\n\n"
                  f"👑 **Owner:** {owner_nik}")
        
        # Notify all admins
        for admin_nik in user_manager.admins:
            admin_data = user_manager.registered_users.get(admin_nik)
            if admin_data:
                admin_user_id = admin_data.get('user_id')
                if admin_user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_user_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                        logger.info(f"Notified admin {admin_nik} about owner {action} action for NIK {nik}")
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin_nik} about owner action: {e}")

    async def _handle_user_removal(self, query, context, data):
        """Handle user removal (owner and admin can do this) with async spreadsheet support"""
        chat_id = query.from_user.id
        
        # Both owner and admin can remove users
        if not (user_manager.is_owner(chat_id) or user_manager.is_admin(chat_id)):
            await query.edit_message_text("Anda tidak memiliki akses untuk menghapus user.")
            return
        
        nik = data.replace("remove_user_", "")
        
        # Get user data before removal for notification
        user_data = user_manager.get_user_by_nik(nik)
        if not user_data:
            await query.edit_message_text(f"❌ User dengan NIK {nik} tidak ditemukan.")
            return
        
        removed_user_id = user_data.get('user_id')
        username = user_data.get('username', 'N/A')
        
        success = await user_manager.remove_user(nik)  # Now async
        
        if success:
            # Notify the removed user
            if removed_user_id:
                try:
                    await context.bot.send_message(
                        chat_id=removed_user_id,
                        text=f"⚠️ Akun Anda telah dihapus dari sistem.\n\n"
                            f"Untuk menggunakan bot kembali, silakan daftar ulang dengan mengirim /start"
                    )
                    logger.info(f"Notified removed user {removed_user_id}")
                except Exception as e:
                    logger.error(f"Failed to notify removed user {removed_user_id}: {e}")
            
            # Get remover details
            remover_role = "owner" if user_manager.is_owner(chat_id) else "admin"
            remover_nik = user_manager.get_user_nik(chat_id) or "owner"
            
            # Cross-notification for user removal
            if user_manager.is_owner(chat_id):
                # Owner removed user - notify all admins
                await self._notify_admins_about_owner_removal(context, nik, username, removed_user_id, remover_nik)
            else:
                # Admin removed user - notify owner
                await self._notify_owner_about_admin_removal(context, nik, username, removed_user_id, remover_role, remover_nik)
            
            await query.edit_message_text(f"✅ User dengan NIK {nik} telah dihapus!")
        else:
            await query.edit_message_text(f"❌ Gagal menghapus user dengan NIK {nik}.")

    async def _notify_owner_about_admin_removal(self, context, nik: str, username: str, removed_user_id: int, admin_role: str, admin_nik: str):
        """Notify owner about user removal by admin"""
        if not user_manager.owner_user_id:
            return
            
        try:
            await context.bot.send_message(
                chat_id=user_manager.owner_user_id,
                text=f"🗑️ **Notifikasi Penghapusan User oleh Admin**\n\n"
                     f"❌ User telah **DIHAPUS** oleh admin.\n\n"
                     f"👤 **Detail User yang Dihapus:**\n"
                     f"• NIK: `{nik}`\n"
                     f"• User ID: `{removed_user_id}`\n"
                     f"• Username: @{username}\n\n"
                     f"🔧 **Admin yang melakukan aksi:**\n"
                     f"• Role: {admin_role}\n"
                     f"• NIK: {admin_nik}",
                parse_mode='Markdown'
            )
            logger.info(f"Notified owner about user removal by admin {admin_nik}")
        except Exception as e:
            logger.error(f"Failed to notify owner about user removal: {e}")

    async def _notify_admins_about_owner_removal(self, context, nik: str, username: str, removed_user_id: int, owner_nik: str):
        """Notify all admins about user removal by owner"""
        message = (f"🗑️ **Notifikasi Penghapusan User oleh Owner**\n\n"
                  f"❌ User telah **DIHAPUS** oleh owner.\n\n"
                  f"👤 **Detail User yang Dihapus:**\n"
                  f"• NIK: `{nik}`\n"
                  f"• User ID: `{removed_user_id}`\n"
                  f"• Username: @{username}\n\n"
                  f"👑 **Owner:** {owner_nik}")
        
        # Notify all admins
        for admin_nik in user_manager.admins:
            admin_data = user_manager.registered_users.get(admin_nik)
            if admin_data:
                admin_user_id = admin_data.get('user_id')
                if admin_user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_user_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                        logger.info(f"Notified admin {admin_nik} about user removal by owner")
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin_nik} about owner removal: {e}")

    async def _handle_admin_removal(self, query, context, data):
        """Handle admin removal (owner only) with async spreadsheet support"""
        if not user_manager.is_owner(query.from_user.id):
            await query.edit_message_text("Hanya owner yang dapat menghapus admin.")
            return
        
        nik = data.replace("remove_admin_", "")
        
        # Get admin data before removal for notification
        user_data = user_manager.get_user_by_nik(nik)
        admin_user_id = user_data.get('user_id') if user_data else None
        admin_username = user_data.get('username', 'N/A') if user_data else 'N/A'
        
        success = await user_manager.remove_admin(nik)  # Now async
        
        if success:
            # Notify the demoted admin
            if admin_user_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_user_id,
                        text=f"⚠️ Status admin Anda telah dicabut.\n\n"
                            f"Anda masih dapat menggunakan bot sebagai employee biasa.",
                        reply_markup=MenuKeyboards.main_menu()
                    )
                    logger.info(f"Notified demoted admin {admin_user_id}")
                except Exception as e:
                    logger.error(f"Failed to notify demoted admin {admin_user_id}: {e}")
            
            # Notify other admins about admin removal by owner
            owner_nik = user_manager.get_user_nik(query.from_user.id) or "owner"
            await self._notify_other_admins_about_admin_removal(context, nik, admin_username, owner_nik)
            
            await query.edit_message_text(f"✅ Admin dengan NIK {nik} telah dihapus!")
        else:
            await query.edit_message_text(f"❌ Gagal menghapus admin dengan NIK {nik}.")


    async def _notify_other_admins_about_admin_removal(self, context, removed_admin_nik: str, admin_username: str, owner_nik: str):
        """Notify other admins about admin removal by owner"""
        message = (f"🔧 **Notifikasi Penghapusan Admin**\n\n"
                  f"➖ Admin telah **DIHAPUS** oleh owner.\n\n"
                  f"🔧 **Admin yang Dihapus:**\n"
                  f"• NIK: `{removed_admin_nik}`\n"
                  f"• Username: @{admin_username}\n\n"
                  f"👑 **Dihapus oleh Owner:** {owner_nik}")
        
        # Notify all remaining admins (except the one being removed)
        for admin_nik in user_manager.admins:
            if admin_nik != removed_admin_nik:  # Don't notify the removed admin
                admin_data = user_manager.registered_users.get(admin_nik)
                if admin_data:
                    admin_user_id = admin_data.get('user_id')
                    if admin_user_id:
                        try:
                            await context.bot.send_message(
                                chat_id=admin_user_id,
                                text=message,
                                parse_mode='Markdown'
                            )
                            logger.info(f"Notified admin {admin_nik} about admin removal by owner")
                        except Exception as e:
                            logger.error(f"Failed to notify admin {admin_nik} about admin removal: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with enhanced registration check"""
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)
        
        logger.info(f"User {chat_id} executed /start command. Current state: {current_state.value}")
        
        if current_state == UserState.UNREGISTERED:
            await update.message.reply_text(Messages.WELCOME_UNREGISTERED)
        elif current_state == UserState.PENDING_APPROVAL:
            await update.message.reply_text(Messages.REGISTRATION_PENDING)
        elif current_state == UserState.REJECTED:
            await update.message.reply_text(Messages.REGISTRATION_REJECTED_CAN_RETRY)
        else:
            # User is approved, show appropriate menu
            user_manager.set_user_state(chat_id, UserState.IDLE)
            user_manager.clear_user_data(chat_id)

            if user_manager.is_owner(chat_id):
                await update.message.reply_text(
                    Messages.OWNER_WELCOME,
                    reply_markup=MenuKeyboards.owner_menu()
                )
            elif user_manager.is_admin(chat_id):
                await update.message.reply_text(
                    Messages.ADMIN_WELCOME,
                    reply_markup=MenuKeyboards.admin_menu()
                )
            else:
                await update.message.reply_text(
                    Messages.WELCOME_APPROVED,
                    reply_markup=MenuKeyboards.main_menu()
                )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        chat_id = update.effective_chat.id
        await update.message.reply_text(
            Messages.HELP_TEXT,
            reply_markup=self._get_appropriate_menu(chat_id)
        )

    async def handle_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user registration with NIK"""
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        current_state = user_manager.get_user_state(chat_id)
        
        # Only handle registration for unregistered or rejected users
        if current_state not in [UserState.UNREGISTERED, UserState.REJECTED]:
            return False  # Not handling registration
        
        # Validate NIK format (6-8 digits)
        if not text.isdigit() or not (6 <= len(text) <= 8):
            await update.message.reply_text(Messages.INVALID_NIK)
            return True
        
        # Register user
        username = update.effective_user.username
        result = user_manager.register_user(chat_id, text, username)
        
        logger.info(f"Registration attempt for user {chat_id}, NIK {text}: {result}")
        
        if result == "invalid_nik":
            await update.message.reply_text(Messages.INVALID_NIK)
        elif result == "already_registered":
            await update.message.reply_text(Messages.NIK_ALREADY_REGISTERED)
        elif result == "already_pending":
            await update.message.reply_text(Messages.REGISTRATION_PENDING)
        elif result == "success":
            user_manager.set_user_state(chat_id, UserState.PENDING_APPROVAL)
            await update.message.reply_text(Messages.REGISTRATION_SUCCESS)
            
            # Notify admins and owner about new registration
            await self._notify_admins_new_registration(context, text, chat_id, username)
        
        return True

    async def _notify_admins_new_registration(self, context, nik: str, user_id: int, username: str):
        """Notify all admins about new registration with inline buttons"""
        message = Messages.ADMIN_APPROVAL_NOTIFICATION.format(
            nik=nik,
            user_id=user_id,
            username=username or "N/A"
        )
        
        # Create inline keyboard for approval
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
                    chat_id=user_manager.owner_user_id,
                    text=message,
                    reply_markup=keyboard
                )
                logger.info(f"Notified owner about new registration: NIK {nik}")
            except Exception as e:
                logger.error(f"Failed to notify owner: {e}")
        
        # Notify all admins
        for nik_admin in user_manager.admins:
            admin_data = user_manager.registered_users.get(nik_admin)
            if admin_data:
                admin_user_id = admin_data.get('user_id')
                if admin_user_id and admin_user_id != user_manager.owner_user_id:  # Don't duplicate for owner
                    try:
                        await context.bot.send_message(
                            chat_id=admin_user_id,
                            text=message,
                            reply_markup=keyboard
                        )
                        logger.info(f"Notified admin {nik_admin} about new registration: NIK {nik}")
                    except Exception as e:
                        logger.error(f"Failed to notify admin {nik_admin}: {e}")

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle media uploads (photos and videos) with sequential validation"""
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)

        # Check if user is authorized
        if not self._is_user_authorized(chat_id):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        if current_state != UserState.WAITING_MEDIA:
            return

        if not user_manager.check_rate_limit(chat_id, Config.RATE_LIMIT_SECONDS):
            await update.message.reply_text(Messages.RATE_LIMIT)
            return

        kendala_type = user_manager.get_user_kendala_type(chat_id)
        if not kendala_type:
            await update.message.reply_text(
                "❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start"
            )
            return

        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")

            # Get media info from message
            file_obj, resource_type, actual_media_type, media_type_name = media_service.get_media_type_info(
                update.message)

            if not file_obj:
                await update.message.reply_text("❌ Hanya foto dan video yang diterima!")
                return

            # Get current step and expected media
            current_step = user_manager.get_user_media_step(chat_id)
            expected_media_info = self.data_processor.get_expected_media_info(kendala_type, current_step)

            if not expected_media_info:
                await update.message.reply_text(
                    "✅ Semua media sudah lengkap! Klik 'Selesai' untuk menyelesaikan.",
                    reply_markup=MenuKeyboards.media_menu()
                )
                return

            field_name, expected_media_type, description = expected_media_info

            # Validate media type matches expectation
            if actual_media_type != expected_media_type:
                expected_name = "Foto" if expected_media_type == "photo" else "Video"
                await update.message.reply_text(
                    f"❌ Media tidak sesuai!\n\n"
                    f"🔸 **Yang diminta**: {expected_name} - {description}\n"
                    f"🔸 **Yang Anda kirim**: {media_type_name}\n\n"
                    f"Silakan kirim {expected_name.lower()} yang sesuai.",
                    reply_markup=MenuKeyboards.media_menu()
                )
                return

            # Upload media dengan better error handling
            try:
                await update.message.reply_text("⏳ Sedang mengunduh dan menyimpan media...")
                media_url = await media_service.download_and_upload_telegram_media(
                    context.bot, file_obj, resource_type
                )
            except Exception as upload_error:
                logger.error(f"Media upload failed for chat_id {chat_id}: {upload_error}")
                await update.message.reply_text(
                    "❌ Gagal mengunduh media. Kemungkinan file terlalu besar atau koneksi bermasalah.\n\n"
                    "Silakan coba lagi dengan file yang lebih kecil atau tunggu beberapa saat.",
                    reply_markup=MenuKeyboards.media_menu()
                )
                return

            # Add media URL to the correct field for current step
            user_manager.add_user_media_url(chat_id, field_name, media_url)

            # Increment step after successful upload
            user_manager.increment_user_media_step(chat_id)

            # Check if we need more media
            new_step = user_manager.get_user_media_step(chat_id)
            total_required = len(MEDIA_FIELDS_WITH_TYPES.get(kendala_type, []))

            if new_step < total_required:
                # Show next required media
                next_media_info = self.data_processor.get_expected_media_info(kendala_type, new_step)
                if next_media_info:
                    field_name_next, expected_type_next, description_next = next_media_info
                    expected_name_next = "Foto" if expected_type_next == "photo" else "Video"

                    await update.message.reply_text(
                        f"✅ {media_type_name} diterima!\n\n"
                        f"🔸 **Langkah {new_step + 1} dari {total_required}**: Kirim {expected_name_next.lower()} - {description_next}",
                        reply_markup=MenuKeyboards.media_menu()
                    )
            else:
                # All media received
                media_count = user_manager.get_user_media_count(chat_id)
                await update.message.reply_text(
                    f"✅ Semua media berhasil diterima ({media_count} file)!\n\n"
                    f"Klik 'Selesai' untuk menyelesaikan input data.",
                    reply_markup=MenuKeyboards.media_menu()
                )

            logger.info(
                f"Media step {current_step} completed for chat_id {chat_id}: {media_url} (Type: {media_type_name})")

        except Exception as e:
            logger.exception(f"Error handling media for chat_id {chat_id}")
            await update.message.reply_text(
                Messages.MEDIA_ERROR,
                reply_markup=MenuKeyboards.media_menu()
            )

    def _is_user_authorized(self, chat_id: int) -> bool:
        """Check if user is authorized to use bot features"""
        current_state = user_manager.get_user_state(chat_id)
        return current_state not in [UserState.UNREGISTERED, UserState.PENDING_APPROVAL, UserState.REJECTED]

    async def menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)

        logger.debug(f"Menu handler: User {chat_id}, Button: {text}, State: {current_state.value}")

        # Handle admin and owner menu options (including new user removal option)
        admin_owner_buttons = [
            "📋 Lihat Pendaftar", "👥 Lihat Admin", "➕ Tambah Admin",
            "🗂️ Kelola User", "➖ Hapus Admin", "🗑️ Hapus User"
        ]
        if text in admin_owner_buttons:
            return await self._handle_admin_buttons(update, context, text)

        # Check authorization for regular menu items
        if not self._is_user_authorized(chat_id):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        # Main menu options
        if text == "🔧 Kendala Teknik":
            user_manager.set_user_state(chat_id, UserState.TEKNIK_SUBMENU)
            await update.message.reply_text(
                Messages.TEKNIK_SUBMENU,
                reply_markup=MenuKeyboards.teknik_menu()
            )

        elif text == "👤 Kendala Pelanggan":
            user_manager.set_user_state(chat_id, UserState.PELANGGAN_SUBMENU)
            await update.message.reply_text(
                Messages.PELANGGAN_SUBMENU,
                reply_markup=MenuKeyboards.pelanggan_menu()
            )

        elif text == "❓ Kendala Lainnya":
            user_manager.set_user_kendala_type(chat_id, KendalaType.LAINNYA)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.LAINNYA),
                reply_markup=MenuKeyboards.back_menu()
            )

        elif text == "🆘 Bantuan":
            user_manager.set_user_state(chat_id, UserState.IDLE)
            await update.message.reply_text(
                Messages.HELP_TEXT,
                reply_markup=self._get_appropriate_menu(chat_id)
            )

        # Teknik submenu options
        elif text == "📶 Tidak ada Jaringan (TAJ)":
            user_manager.set_user_kendala_type(chat_id, KendalaType.TAJ)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.TAJ),
                reply_markup=MenuKeyboards.back_menu()
            )

        # NEW: TAT button now leads to submenu instead of direct input
        elif text == "🏗️ Tidak ada Tiang (TAT)":
            user_manager.set_user_state(chat_id, UserState.TAT_SUBMENU)
            await update.message.reply_text(
                Messages.TAT_SUBMENU,
                reply_markup=MenuKeyboards.tat_menu()
            )

        elif text == "🔌 ODP Full":
            user_manager.set_user_kendala_type(chat_id, KendalaType.ODP_FULL)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.ODP_FULL),
                reply_markup=MenuKeyboards.back_menu()
            )

        # NEW: TAT submenu options
        elif text == "✅ TAT Sudah ACC":
            user_manager.set_user_kendala_type(chat_id, KendalaType.TAT_SUDAH_ACC)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.TAT_SUDAH_ACC),
                reply_markup=MenuKeyboards.back_menu()
            )

        elif text == "❌ TAT Belum ACC":
            user_manager.set_user_kendala_type(chat_id, KendalaType.TAT_BELUM_ACC)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.TAT_BELUM_ACC),
                reply_markup=MenuKeyboards.back_menu()
            )

        # Pelanggan submenu options
        elif text == "😤 Pelanggan Manja":
            user_manager.set_user_kendala_type(chat_id, KendalaType.PELANGGAN_MANJA)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.PELANGGAN_MANJA),
                reply_markup=MenuKeyboards.back_menu()
            )

        elif text == "❌ Pelanggan Cancel":
            user_manager.set_user_kendala_type(chat_id, KendalaType.PELANGGAN_CANCEL)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.PELANGGAN_CANCEL),
                reply_markup=MenuKeyboards.back_menu()
            )

        elif text == "🔄 Cabut Pasang":
            user_manager.set_user_kendala_type(chat_id, KendalaType.CABUT_PASANG)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.CABUT_PASANG),
                reply_markup=MenuKeyboards.back_menu()
            )

        # Media menu - "✅ Selesai"
        elif text == "✅ Selesai":
            await self._handle_finish_media(update, context, chat_id)

        # Navigation
        elif text == "🏠 Menu Utama":
            user_manager.set_user_state(chat_id, UserState.IDLE)
            user_manager.clear_user_data(chat_id)
            await update.message.reply_text(
                "🏠 Kembali ke menu utama",
                reply_markup=self._get_appropriate_menu(chat_id)
            )

    def _get_appropriate_menu(self, chat_id: int):
        """Get appropriate menu based on user role"""
        if user_manager.is_owner(chat_id):
            return MenuKeyboards.owner_menu()
        elif user_manager.is_admin(chat_id):
            return MenuKeyboards.admin_menu()
        else:
            return MenuKeyboards.main_menu()

    async def _handle_admin_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle admin menu buttons with enhanced functionality"""
        chat_id = update.effective_chat.id
        
        # Check admin permissions
        if not (user_manager.is_owner(chat_id) or user_manager.is_admin(chat_id)):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return True

        if text == "📋 Lihat Pendaftar":
            await self._show_pending_registrations(update)

        elif text == "👥 Lihat Admin" and user_manager.is_owner(chat_id):
            await self._show_admin_list(update)

        elif text == "➕ Tambah Admin" and user_manager.is_owner(chat_id):
            user_manager.set_user_state(chat_id, UserState.WAITING_ADMIN_NIK)
            await update.message.reply_text(Messages.ADD_ADMIN_REQUEST)

        elif text == "🗂️ Kelola User" and user_manager.is_owner(chat_id):
            await self._show_user_management(update)

        elif text == "➖ Hapus Admin" and user_manager.is_owner(chat_id):
            await self._show_admin_removal_options(update)

        elif text == "🗑️ Hapus User":
            # Both owner and admin can access this
            await self._show_user_removal_options(update)

        return True

    async def _show_pending_registrations(self, update: Update):
        """Show pending registrations with inline buttons"""
        pending = user_manager.get_pending_registrations()
        if not pending:
            await update.message.reply_text("Tidak ada pendaftar yang menunggu approval.")
        else:
            for i, registration in enumerate(pending):
                nik = registration['nik']
                username = registration.get('username', 'N/A')
                user_id = registration['user_id']
                
                # Create individual message for each pending registration
                message = f"📋 **Pendaftaran #{i+1}**\n\n"
                message += f"NIK: `{nik}`\n"
                message += f"User ID: `{user_id}`\n"
                message += f"Username: @{username}\n"
                message += f"Waktu: {self._format_timestamp(registration['timestamp'])}"
                
                # Create inline keyboard for this registration
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Setujui", callback_data=f"approve_{nik}"),
                        InlineKeyboardButton("❌ Tolak", callback_data=f"reject_{nik}")
                    ]
                ])
                
                await update.message.reply_text(
                    message, 
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )

    async def _show_admin_list(self, update: Update):
        """Show admin list with removal options for owner"""
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

    async def _show_user_management(self, update: Update):
        """Show user management options for owner"""
        all_users = user_manager.get_all_users_list()
        if not all_users:
            await update.message.reply_text("Belum ada user yang terdaftar.")
            return

        # Show users with management options
        message = "🗂️ **Kelola User (Daftar Semua User):**\n\n"
        
        for i, user in enumerate(all_users[:10], 1):  # Limit to 10 users per message
            role_emoji = "👑" if user['role'] == "owner" else "🔧" if user['role'] == "admin" else "👤"
            message += f"{i}. {role_emoji} NIK: `{user['nik']}`\n"
            message += f"   Username: @{user.get('username', 'N/A')}\n"
            message += f"   Role: {user['role'].title()}\n"
            message += f"   Status: {user['status'].title()}\n\n"

        if len(all_users) > 10:
            message += f"... dan {len(all_users) - 10} user lainnya\n\n"

        message += "💡 Gunakan menu untuk mengelola admin dan user."
        
        await update.message.reply_text(message, parse_mode='Markdown')

    async def _show_admin_removal_options(self, update: Update):
        """Show admin removal options for owner"""
        admin_list = user_manager.get_admin_list()
        if not admin_list:
            await update.message.reply_text("Tidak ada admin yang dapat dihapus.")
            return

        # Create inline buttons for admin removal
        buttons = []
        for admin in admin_list[:5]:  # Limit to 5 admins per row
            nik = admin['nik']
            username = admin.get('username', nik)
            buttons.append([
                InlineKeyboardButton(
                    f"❌ Hapus {username} ({nik})", 
                    callback_data=f"remove_admin_{nik}"
                )
            ])

        keyboard = InlineKeyboardMarkup(buttons)
        
        await update.message.reply_text(
            "➖ **Hapus Admin**\n\nPilih admin yang aakan dihapus:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )

    async def _show_user_removal_options(self, update: Update):
        """Show user removal options for owner and admin"""
        all_users = user_manager.get_all_users_list()
        if not all_users:
            await update.message.reply_text("Tidak ada user yang dapat dihapus.")
            return

        # Create inline buttons for user removal
        buttons = []
        for user in all_users[:10]:  # Limit to 10 users to avoid message length issues
            nik = user['nik']
            username = user.get('username', nik)
            role_emoji = "👑" if user['role'] == "owner" else "🔧" if user['role'] == "admin" else "👤"
            
            # Don't allow removal of owner
            if user['role'] != "owner":
                buttons.append([
                    InlineKeyboardButton(
                        f"🗑️ {role_emoji} {username} ({nik})", 
                        callback_data=f"remove_user_{nik}"
                    )
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

    async def handle_admin_nik_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin NIK input from owner with async spreadsheet support"""
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        
        if user_manager.get_user_state(chat_id) != UserState.WAITING_ADMIN_NIK or not user_manager.is_owner(chat_id):
            return False
        
        # Validate NIK format (6-8 digits)
        if not text.isdigit() or not (6 <= len(text) <= 8):
            await update.message.reply_text(Messages.INVALID_NIK)
            return True
        
        # Try to add admin
        success = await user_manager.add_admin(text)  # Now async
        user_manager.set_user_state(chat_id, UserState.IDLE)
        
        if success:
            await update.message.reply_text(
                Messages.ADMIN_ADDED.format(nik=text) + "\n\n📊 Data admin telah disinkronkan ke spreadsheet.",
                reply_markup=MenuKeyboards.owner_menu()
            )
            
            # Notify the new admin
            user_data = user_manager.get_user_by_nik(text)
            if user_data and user_data.get('user_id'):
                try:
                    await context.bot.send_message(
                        chat_id=user_data['user_id'],
                        text=f"🔧 Anda telah ditunjuk sebagai admin!\n\nSekarang Anda memiliki akses ke fitur admin.",
                        reply_markup=MenuKeyboards.admin_menu()
                    )
                    logger.info(f"Notified new admin {text} about role assignment")
                except Exception as e:
                    logger.error(f"Failed to notify new admin {text}: {e}")
                    
            # Notify other admins about new admin addition
            owner_nik = user_manager.get_user_nik(chat_id) or "owner"
            await self._notify_admins_about_new_admin(context, text, user_data.get('username', 'N/A'), owner_nik)
            
        else:
            await update.message.reply_text(
                Messages.ADMIN_ADD_ERROR,
                reply_markup=MenuKeyboards.owner_menu()
            )
        
        return True

    async def _notify_admins_about_new_admin(self, context, new_admin_nik: str, new_admin_username: str, owner_nik: str):
        """Notify existing admins about new admin addition by owner"""
        message = (f"🔧 **Notifikasi Admin Baru**\n\n"
                  f"➕ Admin baru telah **DITAMBAHKAN** oleh owner.\n\n"
                  f"🔧 **Admin Baru:**\n"
                  f"• NIK: `{new_admin_nik}`\n"
                  f"• Username: @{new_admin_username}\n\n"
                  f"👑 **Ditambahkan oleh Owner:** {owner_nik}")
        
        # Notify all existing admins (except the new one)
        for admin_nik in user_manager.admins:
            if admin_nik != new_admin_nik:  # Don't notify the new admin about themselves
                admin_data = user_manager.registered_users.get(admin_nik)
                if admin_data:
                    admin_user_id = admin_data.get('user_id')
                    if admin_user_id:
                        try:
                            await context.bot.send_message(
                                chat_id=admin_user_id,
                                text=message,
                                parse_mode='Markdown'
                            )
                            logger.info(f"Notified admin {admin_nik} about new admin addition")
                        except Exception as e:
                            logger.error(f"Failed to notify admin {admin_nik} about new admin: {e}")

    async def _handle_finish_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        """Handle finish media button with validation"""
        kendala_type = user_manager.get_user_kendala_type(chat_id)
        if not kendala_type:
            await update.message.reply_text(
                "❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start"
            )
            return

        current_step = user_manager.get_user_media_step(chat_id)
        total_required = len(MEDIA_FIELDS_WITH_TYPES.get(kendala_type, []))

        # Check if all required media have been uploaded
        if current_step < total_required:
            # Show remaining requirements
            remaining_media = []
            for i in range(current_step, total_required):
                media_info = self.data_processor.get_expected_media_info(kendala_type, i)
                if media_info:
                    _, media_type, desc = media_info
                    type_name = "📸 Foto" if media_type == "photo" else "🎥 Video"
                    remaining_media.append(f"{i + 1}. {type_name}: {desc}")

            await update.message.reply_text(
                f"⚠️ Masih ada media yang belum dikirim:\n\n" +
                "\n".join(remaining_media),
                reply_markup=MenuKeyboards.media_menu()
            )
            return

        # All media completed - proceed with saving
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            
            last_row = user_manager.get_user_last_row(chat_id)
            media_urls_dict = user_manager.get_user_media_urls(chat_id)
            sheet_name = user_manager.get_user_sheet_name(chat_id)

            if last_row > 0 and kendala_type and sheet_name:
                # Get sheet columns for this kendala type
                sheet_columns = self.data_processor.get_sheet_columns(kendala_type)
                
                # Update each media column
                for media_field in MEDIA_FIELDS[kendala_type]:
                    if media_field in sheet_columns:
                        column_index = sheet_columns.index(media_field)
                        urls = media_urls_dict.get(media_field, [])
                        if urls:  # Only update if there are URLs
                            await sheets_service.update_cell(last_row, column_index, urls, sheet_name)
                            logger.info(f"Updated {media_field} for row {last_row} with {len(urls)} URLs")

            user_manager.set_user_state(chat_id, UserState.IDLE)
            media_count = user_manager.get_user_media_count(chat_id)
            
            # Log completion
            user_nik = user_manager.get_user_nik(chat_id)
            parsed_data = user_manager.get_user_parsed_data(chat_id)
            sc_number = parsed_data.get('SC', 'N/A') if parsed_data else 'N/A'
            
            logger.info(f"Completed data entry - NIK: {user_nik}, SC: {sc_number}, Kendala: {kendala_type.value}, Media: {media_count}")
            
            await update.message.reply_text(
                f"✅ Data berhasil disimpan lengkap dengan {media_count} media!\n\n"
                f"📊 **Ringkasan:**\n"
                f"• SC: {sc_number}\n"
                f"• Kendala: {kendala_type.value.upper()}\n"
                f"• Media: {media_count} file",
                reply_markup=self._get_appropriate_menu(chat_id)
            )

            user_manager.clear_user_data(chat_id)

        except Exception as e:
            logger.exception(f"Error finishing data entry for chat_id {chat_id}")
            await update.message.reply_text(
                "❌ Terjadi kesalahan saat menyelesaikan data. Silakan coba lagi.",
                reply_markup=MenuKeyboards.media_menu()
            )

    async def handle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input for data entry and registration"""
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)
        text = update.message.text.strip()

        logger.debug(f"Input handler: User {chat_id}, State: {current_state.value}, Text length: {len(text)}")

        # Handle registration (includes re-registration after rejection)
        if current_state in [UserState.UNREGISTERED, UserState.REJECTED]:
            return await self.handle_registration(update, context)

        # Handle admin NIK input
        if current_state == UserState.WAITING_ADMIN_NIK:
            return await self.handle_admin_nik_input(update, context)

        # Check authorization for data entry
        if not self._is_user_authorized(chat_id):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        if current_state != UserState.WAITING_INPUT:
            return

        if not user_manager.check_rate_limit(chat_id, Config.RATE_LIMIT_SECONDS):
            await update.message.reply_text(Messages.RATE_LIMIT)
            return

        kendala_type = user_manager.get_user_kendala_type(chat_id)
        if not kendala_type:
            await update.message.reply_text(
                "❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start"
            )
            return

        # Parse and validate input
        parsed_data = self.data_processor.parse_input(text, kendala_type)
        
        # Add NIK from registration data
        user_nik = user_manager.get_user_nik(chat_id)
        if user_nik:
            parsed_data['NIK'] = user_nik
        
        validation_errors = self.data_processor.validate_input(parsed_data, kendala_type)

        if validation_errors:
            error_message = "⚠️ " + "\n".join(validation_errors) + "\n\n" + self.data_processor.get_input_format(kendala_type)
            await update.message.reply_text(error_message)
            return

        # Store parsed data for later use
        user_manager.set_user_parsed_data(chat_id, parsed_data)

        # Save to Google Sheets
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")

            # Get target sheet name and prepare data
            sheet_name = self.data_processor.get_target_sheet_name(kendala_type)
            row_data = self.data_processor.prepare_sheet_data(parsed_data, kendala_type)

            # Save to appropriate sheet
            last_row = await sheets_service.append_row(row_data, sheet_name)
            user_manager.set_user_last_row(chat_id, last_row)
            user_manager.set_user_sheet_name(chat_id, sheet_name)

            if last_row > 0:
                # Change state to waiting for media
                user_manager.set_user_state(chat_id, UserState.WAITING_MEDIA)
                user_manager.set_user_media_step(chat_id, 0)  # Start from step 0

                logger.info(f"Starting media collection for chat_id {chat_id}, kendala_type: {kendala_type.value}, sheet: {sheet_name}, row: {last_row}")

                await update.message.reply_text(
                    self.data_processor.get_media_prompt(kendala_type, 0),
                    reply_markup=MenuKeyboards.media_menu(),
                    parse_mode='Markdown'
                )

                # Log successful data entry
                logger.info(
                    f"Data saved for chat_id {chat_id}: SC={parsed_data.get('SC')}, Kendala={kendala_type.value}, NIK={parsed_data.get('NIK')}, Row={last_row}")

        except gspread.exceptions.APIError as e:
            logger.error(f"Google Sheets API error for chat_id {chat_id}: {e}")
            await update.message.reply_text(
                "❌ Error API Google Sheets. Silakan coba lagi dalam beberapa saat.",
                reply_markup=MenuKeyboards.back_menu()
            )

        except Exception as e:
            logger.exception(f"Unexpected error for chat_id {chat_id}")
            await update.message.reply_text(
                "❌ Terjadi kesalahan tidak terduga. Silakan coba lagi atau hubungi admin.",
                reply_markup=MenuKeyboards.back_menu()
            )

    async def fallback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unrecognized commands or messages"""
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)

        logger.debug(f"Fallback handler: User {chat_id}, State: {current_state.value}")

        # Handle unregistered users
        if current_state == UserState.UNREGISTERED:
            await update.message.reply_text(Messages.WELCOME_UNREGISTERED)
            return
        elif current_state == UserState.PENDING_APPROVAL:
            await update.message.reply_text(Messages.REGISTRATION_PENDING)
            return
        elif current_state == UserState.REJECTED:
            await update.message.reply_text(Messages.REGISTRATION_REJECTED_CAN_RETRY)
            return

        # Check authorization
        if not self._is_user_authorized(chat_id):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        if current_state == UserState.WAITING_INPUT:
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
        elif current_state == UserState.WAITING_MEDIA:
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
        elif current_state == UserState.WAITING_ADMIN_NIK:
            await update.message.reply_text(
                "📝 Silakan kirim NIK yang valid (6-8 digit) untuk admin baru:",
                reply_markup=MenuKeyboards.back_menu()
            )
        else:
            await update.message.reply_text(
                "❓ Perintah tidak dikenali. Gunakan menu di bawah atau ketik /start",
                reply_markup=self._get_appropriate_menu(chat_id)
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

    def _format_timestamp(self, timestamp: float) -> str:
        """Format timestamp for display"""
        import datetime
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

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
                    'idle': '💤',
                    'waiting_input': '✏️',
                    'waiting_media': '📸',
                    'pending_approval': '⏳',
                    'rejected': '❌',
                    'unregistered': '🚫'
                }.get(state, '📊')
                message += f"• {state_emoji} {state.replace('_', ' ').title()}: {count}\n"
        
        if stats['kendala_types']:
            message += "\n📋 **Jenis Kendala Aktif:**\n"
            for kendala, count in stats['kendala_types'].items():
                kendala_emoji = {
                    'taj': '📶',
                    'tat': '🏗️',
                    'odp_full': '🔌',
                    'pelanggan_manja': '😤',
                    'pelanggan_cancel': '❌',
                    'cabut_pasang': '🔄',
                    'lainnya': '❓'
                }.get(kendala, '📊')
                message += f"• {kendala_emoji} {kendala.upper()}: {count}\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cleanup command for owner (cleanup old sessions)"""
        chat_id = update.effective_chat.id
        
        if not user_manager.is_owner(chat_id):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        # Cleanup sessions older than 24 hours
        user_manager.cleanup_old_sessions(24)
        
        await update.message.reply_text(
            "🧹 Session cleanup completed!\n\n"
            "Inactive sessions older than 24 hours have been removed."
        )

    def validate_user_access(self, chat_id: int, required_role: UserRole = UserRole.EMPLOYEE) -> bool:
        """Validate user access level"""
        user_role = user_manager.get_user_role(chat_id)
        
        if not user_role:
            return False
        
        if required_role == UserRole.OWNER:
            return user_role == UserRole.OWNER
        elif required_role == UserRole.ADMIN:
            return user_role in [UserRole.ADMIN, UserRole.OWNER]
        else:  # EMPLOYEE
            return user_role in [UserRole.EMPLOYEE, UserRole.ADMIN, UserRole.OWNER]

    async def handle_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unknown commands"""
        chat_id = update.effective_chat.id
        command = update.message.text
        
        logger.warning(f"Unknown command from user {chat_id}: {command}")
        
        await update.message.reply_text(
            f"❓ Command tidak dikenal: {command}\n\n"
            "Available commands:\n"
            "• /start - Mulai ulang bot\n"
            "• /help - Bantuan\n" +
            ("• /stats - Lihat statistik\n• /cleanup - Cleanup sessions\n" if self.validate_user_access(chat_id, UserRole.ADMIN) else ""),
            reply_markup=self._get_appropriate_menu(chat_id)
        )

    def get_user_context_info(self, chat_id: int) -> dict:
        """Get comprehensive user context information for debugging"""
        return {
            'user_id': chat_id,
            'state': user_manager.get_user_state(chat_id).value,
            'nik': user_manager.get_user_nik(chat_id),
            'role': user_manager.get_user_role(chat_id).value if user_manager.get_user_role(chat_id) else None,
            'is_owner': user_manager.is_owner(chat_id),
            'is_admin': user_manager.is_admin(chat_id),
            'is_registered': user_manager.is_user_registered(chat_id),
            'is_pending': user_manager.is_user_pending(chat_id),
            'kendala_type': user_manager.get_user_kendala_type(chat_id).value if user_manager.get_user_kendala_type(chat_id) else None,
            'media_step': user_manager.get_user_media_step(chat_id),
            'media_count': user_manager.get_user_media_count(chat_id)
        }


# Global instance
bot_handlers = BotHandlers()