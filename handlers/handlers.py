import logging
import gspread
from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from constants import (
    UserState,
    KendalaType,
    Messages,
    MenuKeyboards,
    MEDIA_FIELDS_WITH_TYPES,
    MEDIA_FIELDS
)
from user_state_manager import user_manager
from services.sheets_service import sheets_service
from services.media_service import media_service
from utils.data_processor import DataProcessor

logger = logging.getLogger(__name__)


class BotHandlers:
    """Bot message handlers class"""

    def __init__(self):
        self.data_processor = DataProcessor()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        chat_id = update.effective_chat.id
        user_manager.set_user_state(chat_id, UserState.IDLE)
        user_manager.clear_user_data(chat_id)

        await update.message.reply_text(
            Messages.WELCOME,
            reply_markup=MenuKeyboards.main_menu()
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(Messages.HELP_TEXT)

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle media uploads (photos and videos)"""
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)

        # Debug logging
        user_manager.debug_user_state(chat_id)

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

    async def menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button clicks"""
        text = update.message.text
        chat_id = update.effective_chat.id

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
                reply_markup=MenuKeyboards.main_menu()
            )

        # Teknik submenu options
        elif text == "📶 Tidak ada Jaringan (TAJ)":
            user_manager.set_user_kendala_type(chat_id, KendalaType.TAJ)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.TAJ),
                reply_markup=MenuKeyboards.back_menu()
            )

        elif text == "🏗️ Tidak ada Tiang (TAT)":
            user_manager.set_user_kendala_type(chat_id, KendalaType.TAT)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.TAT),
                reply_markup=MenuKeyboards.back_menu()
            )

        elif text == "🔌 ODP Full":
            user_manager.set_user_kendala_type(chat_id, KendalaType.ODP_FULL)
            user_manager.set_user_state(chat_id, UserState.WAITING_INPUT)
            await update.message.reply_text(
                self.data_processor.get_input_format(KendalaType.ODP_FULL),
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
            await update.message.reply_text(
                "🏠 Kembali ke menu utama",
                reply_markup=MenuKeyboards.main_menu()
            )
            user_manager.clear_user_data(chat_id)

    async def _handle_finish_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        """Handle finish media button"""
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
                        await sheets_service.update_cell(last_row, column_index, urls, sheet_name)

            user_manager.set_user_state(chat_id, UserState.IDLE)
            media_count = user_manager.get_user_media_count(chat_id)
            await update.message.reply_text(
                f"✅ Data berhasil disimpan lengkap dengan {media_count} media!",
                reply_markup=MenuKeyboards.main_menu()
            )

            user_manager.clear_user_data(chat_id)

        except Exception as e:
            logger.exception(f"Error finishing data entry for chat_id {chat_id}")
            await update.message.reply_text(
                "❌ Terjadi kesalahan saat menyelesaikan data. Silakan coba lagi.",
                reply_markup=MenuKeyboards.media_menu()
            )

    async def handle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input for data entry"""
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)

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
        parsed_data = self.data_processor.parse_input(update.message.text, kendala_type)
        validation_errors = self.data_processor.validate_input(parsed_data, kendala_type)

        if validation_errors:
            error_message = "⚠️ " + "\n".join(validation_errors) + "\n\n" + self.data_processor.get_input_format(
                kendala_type)
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

                logger.info(f"Starting media collection for chat_id {chat_id}, kendala_type: {kendala_type.value}, sheet: {sheet_name}")

                await update.message.reply_text(
                    self.data_processor.get_media_prompt(kendala_type, 0),
                    reply_markup=MenuKeyboards.media_menu(),
                    parse_mode='Markdown'
                )

                # Log successful data entry
                logger.info(
                    f"Data saved for chat_id {chat_id}: SC={parsed_data.get('SC')}, Kendala={kendala_type.value}, NIK={parsed_data.get('NIK')}")

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

        if current_state == UserState.WAITING_INPUT:
            kendala_type = user_manager.get_user_kendala_type(chat_id)
            if kendala_type:
                await update.message.reply_text(
                    "⚠️ Format data tidak dikenali. " + self.data_processor.get_input_format(kendala_type),
                    reply_markup=MenuKeyboards.back_menu()
                )
            else:
                await update.message.reply_text(
                    "❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start",
                    reply_markup=MenuKeyboards.main_menu()
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
                        f"📸 Kirim media dokumentasi sesuai urutan!\n\n🔸 **Yang diminta sekarang**: {media_name} - {description}",
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
                    reply_markup=MenuKeyboards.main_menu()
                )
        else:
            await update.message.reply_text(
                "❓ Perintah tidak dikenali. Gunakan menu di bawah atau ketik /start",
                reply_markup=MenuKeyboards.main_menu()
            )

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors caused by Updates."""
        logger.error(f"Update {update} caused error {context.error}")


# Global instance
bot_handlers = BotHandlers()