from .base_handler import BaseHandler, logger, user_manager, ContextTypes, Update, UserState, Messages, MenuKeyboards


class AuthHandler(BaseHandler):
    """Handle authentication and registration"""

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
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
            user_manager.set_user_state(chat_id, UserState.IDLE)
            user_manager.clear_user_data(chat_id)

            if user_manager.is_owner(chat_id):
                await update.message.reply_text(Messages.OWNER_WELCOME, reply_markup=MenuKeyboards.owner_menu())
            elif user_manager.is_admin(chat_id):
                await update.message.reply_text(Messages.ADMIN_WELCOME, reply_markup=MenuKeyboards.admin_menu())
            else:
                await update.message.reply_text(Messages.WELCOME_APPROVED, reply_markup=MenuKeyboards.main_menu())

    async def handle_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user registration with NIK"""
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        current_state = user_manager.get_user_state(chat_id)

        if current_state not in [UserState.UNREGISTERED, UserState.REJECTED]:
            return False

        if not text.isdigit() or not (6 <= len(text) <= 8):
            await update.message.reply_text(Messages.INVALID_NIK)
            return True

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

            # Notify admins about new registration
            from .notification_handler import NotificationHandler
            await NotificationHandler()._notify_admins_new_registration(context, text, chat_id, username)

        return True
