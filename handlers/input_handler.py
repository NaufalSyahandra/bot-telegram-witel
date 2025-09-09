from .base_handler import BaseHandler, UserState, Messages, MenuKeyboards, Update, ContextTypes, user_manager, logger
from utils.data_processor import DataProcessor
from services.sheets_service import sheets_service
from config import Config
import gspread


class InputHandler(BaseHandler):
    """Handle text input for data entry"""

    def __init__(self):
        self.data_processor = DataProcessor()

    async def handle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input for data entry and registration"""
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)
        text = update.message.text.strip()

        logger.debug(f"Input handler: User {chat_id}, State: {current_state.value}, Text length: {len(text)}")

        # Route to appropriate handler based on state
        if current_state in [UserState.UNREGISTERED, UserState.REJECTED]:
            from .auth_handler import AuthHandler
            return await AuthHandler().handle_registration(update, context)

        elif current_state == UserState.WAITING_ADMIN_NIK:
            from .admin_handler import AdminHandler
            return await AdminHandler().handle_admin_nik_input(update, context)

        elif current_state == UserState.WAITING_INPUT:
            return await self._handle_data_input(update, context, text, chat_id)

        return False

    async def _handle_data_input(self, update, context, text, chat_id):
        """Handle data input for kendala reporting"""
        if not self._is_user_authorized(chat_id):
            await update.message.reply_text(Messages.UNAUTHORIZED)
            return True

        if not user_manager.check_rate_limit(chat_id, Config.RATE_LIMIT_SECONDS):
            await update.message.reply_text(Messages.RATE_LIMIT)
            return True

        kendala_type = user_manager.get_user_kendala_type(chat_id)
        if not kendala_type:
            await update.message.reply_text("❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start")
            return True

        # Parse and validate input
        parsed_data = self.data_processor.parse_input(text, kendala_type)

        # Add NIK from registration
        user_nik = user_manager.get_user_nik(chat_id)
        if user_nik:
            parsed_data['NIK'] = user_nik

        validation_errors = self.data_processor.validate_input(parsed_data, kendala_type)

        if validation_errors:
            error_message = "⚠️ " + "\n".join(validation_errors) + "\n\n" + self.data_processor.get_input_format(
                kendala_type)
            await update.message.reply_text(error_message)
            return True

        # Save data and proceed to media collection
        await self._save_and_proceed_to_media(update, context, parsed_data, chat_id, kendala_type)
        return True

    async def _save_and_proceed_to_media(self, update, context, parsed_data, chat_id, kendala_type):
        """Save data to sheets and proceed to media collection"""
        user_manager.set_user_parsed_data(chat_id, parsed_data)

        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")

            # Get target sheet and prepare data
            sheet_name = self.data_processor.get_target_sheet_name(kendala_type)
            row_data = self.data_processor.prepare_sheet_data(parsed_data, kendala_type)

            # Save to sheet
            last_row = await sheets_service.append_row(row_data, sheet_name)
            user_manager.set_user_last_row(chat_id, last_row)
            user_manager.set_user_sheet_name(chat_id, sheet_name)

            if last_row > 0:
                # Proceed to media collection
                user_manager.set_user_state(chat_id, UserState.WAITING_MEDIA)
                user_manager.set_user_media_step(chat_id, 0)

                logger.info(
                    f"Starting media collection for chat_id {chat_id}, kendala_type: {kendala_type.value}, sheet: {sheet_name}, row: {last_row}")

                await update.message.reply_text(
                    self.data_processor.get_media_prompt(kendala_type, 0),
                    reply_markup=MenuKeyboards.media_menu(),
                    parse_mode='Markdown'
                )

                logger.info(
                    f"Data saved for chat_id {chat_id}: SC={parsed_data.get('SC')}, Kendala={kendala_type.value}, NIK={parsed_data.get('NIK')}, Row={last_row}")

        except gspread.exceptions.APIError as e:
            logger.error(f"Google Sheets API error for chat_id {chat_id}: {e}")
            await update.message.reply_text("❌ Error API Google Sheets. Silakan coba lagi dalam beberapa saat.",
                                            reply_markup=MenuKeyboards.back_menu())
        except Exception as e:
            logger.exception(f"Unexpected error for chat_id {chat_id}")
            await update.message.reply_text("❌ Terjadi kesalahan tidak terduga. Silakan coba lagi atau hubungi admin.",
                                            reply_markup=MenuKeyboards.back_menu())
