from .base_handler import BaseHandler, UserState, MenuKeyboards, Update, ContextTypes, user_manager, Messages, logger
from constants import MEDIA_FIELDS_WITH_TYPES, MEDIA_FIELDS
from services.media_service import media_service
from services.sheets_service import sheets_service
from utils.data_processor import DataProcessor
from config import Config


class MediaHandler(BaseHandler):
    """Handle media uploads and processing"""

    def __init__(self):
        self.data_processor = DataProcessor()

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle media uploads with sequential validation"""
        chat_id = update.effective_chat.id
        current_state = user_manager.get_user_state(chat_id)

        if not self._is_user_authorized(chat_id) or current_state != UserState.WAITING_MEDIA:
            if not self._is_user_authorized(chat_id):
                await update.message.reply_text(Messages.UNAUTHORIZED)
            return

        if not user_manager.check_rate_limit(chat_id, Config.RATE_LIMIT_SECONDS):
            await update.message.reply_text(Messages.RATE_LIMIT)
            return

        kendala_type = user_manager.get_user_kendala_type(chat_id)
        if not kendala_type:
            await update.message.reply_text("❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start")
            return

        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")

            # Get media info and validate
            file_obj, resource_type, actual_media_type, media_type_name = media_service.get_media_type_info(
                update.message)
            if not file_obj:
                await update.message.reply_text("❌ Hanya foto dan video yang diterima!")
                return

            # Validate media type and step
            if not await self._validate_media_step(update, chat_id, kendala_type, actual_media_type, media_type_name):
                return

            # Process media upload
            await self._process_media_upload(update, context, chat_id, file_obj, resource_type, kendala_type,
                                             media_type_name)

        except Exception as e:
            logger.exception(f"Error handling media for chat_id {chat_id}")
            await update.message.reply_text(Messages.MEDIA_ERROR, reply_markup=MenuKeyboards.media_menu())

    async def _validate_media_step(self, update, chat_id, kendala_type, actual_media_type, media_type_name):
        """Validate current media step and type"""
        current_step = user_manager.get_user_media_step(chat_id)
        expected_media_info = self.data_processor.get_expected_media_info(kendala_type, current_step)

        if not expected_media_info:
            await update.message.reply_text(
                "✅ Semua media sudah lengkap! Klik 'Selesai' untuk menyelesaikan.",
                reply_markup=MenuKeyboards.media_menu()
            )
            return False

        field_name, expected_media_type, description = expected_media_info

        if actual_media_type != expected_media_type:
            expected_name = "Foto" if expected_media_type == "photo" else "Video"
            await update.message.reply_text(
                f"❌ Media tidak sesuai!\n\n"
                f"🔸 **Yang diminta**: {expected_name} - {description}\n"
                f"🔸 **Yang Anda kirim**: {media_type_name}\n\n"
                f"Silakan kirim {expected_name.lower()} yang sesuai.",
                reply_markup=MenuKeyboards.media_menu()
            )
            return False

        return True

    async def _process_media_upload(self, update, context, chat_id, file_obj, resource_type, kendala_type,
                                    media_type_name):
        """Process media upload and update state"""
        try:
            await update.message.reply_text("⏳ Sedang mengunduh dan menyimpan media...")
            media_url = await media_service.download_and_upload_telegram_media(context.bot, file_obj, resource_type)
        except Exception as upload_error:
            logger.error(f"Media upload failed for chat_id {chat_id}: {upload_error}")
            await update.message.reply_text(
                "❌ Gagal mengunduh media. Kemungkinan file terlalu besar atau koneksi bermasalah.\n\n"
                "Silakan coba lagi dengan file yang lebih kecil atau tunggu beberapa saat.",
                reply_markup=MenuKeyboards.media_menu()
            )
            return

        # Update user data
        current_step = user_manager.get_user_media_step(chat_id)
        expected_media_info = self.data_processor.get_expected_media_info(kendala_type, current_step)
        field_name = expected_media_info[0]

        user_manager.add_user_media_url(chat_id, field_name, media_url)
        user_manager.increment_user_media_step(chat_id)

        # Check next step
        await self._handle_next_media_step(update, chat_id, kendala_type, media_type_name)

    async def _handle_next_media_step(self, update, chat_id, kendala_type, media_type_name):
        """Handle next media step or completion"""
        new_step = user_manager.get_user_media_step(chat_id)
        total_required = len(MEDIA_FIELDS_WITH_TYPES.get(kendala_type, []))

        if new_step < total_required:
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
            media_count = user_manager.get_user_media_count(chat_id)
            await update.message.reply_text(
                f"✅ Semua media berhasil diterima ({media_count} file)!\n\n"
                f"Klik 'Selesai' untuk menyelesaikan input data.",
                reply_markup=MenuKeyboards.media_menu()
            )

    async def handle_finish_media(self, update, context, chat_id):
        """Handle finish media button with validation"""
        kendala_type = user_manager.get_user_kendala_type(chat_id)
        if not kendala_type:
            await update.message.reply_text("❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start")
            return

        current_step = user_manager.get_user_media_step(chat_id)
        total_required = len(MEDIA_FIELDS_WITH_TYPES.get(kendala_type, []))

        # Check if all required media have been uploaded
        if current_step < total_required:
            remaining_media = []
            for i in range(current_step, total_required):
                media_info = self.data_processor.get_expected_media_info(kendala_type, i)
                if media_info:
                    _, media_type, desc = media_info
                    type_name = "📸 Foto" if media_type == "photo" else "🎥 Video"
                    remaining_media.append(f"{i + 1}. {type_name}: {desc}")

            await update.message.reply_text(
                f"⚠️ Masih ada media yang belum dikirim:\n\n" + "\n".join(remaining_media),
                reply_markup=MenuKeyboards.media_menu()
            )
            return

        # Process completion
        await self._complete_data_entry(update, context, chat_id, kendala_type)

    async def _complete_data_entry(self, update, context, chat_id, kendala_type):
        """Complete data entry with media"""
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")

            last_row = user_manager.get_user_last_row(chat_id)
            media_urls_dict = user_manager.get_user_media_urls(chat_id)
            sheet_name = user_manager.get_user_sheet_name(chat_id)

            if last_row > 0 and kendala_type and sheet_name:
                sheet_columns = self.data_processor.get_sheet_columns(kendala_type)

                # Update each media column
                for media_field in MEDIA_FIELDS[kendala_type]:
                    if media_field in sheet_columns:
                        column_index = sheet_columns.index(media_field)
                        urls = media_urls_dict.get(media_field, [])
                        if urls:
                            await sheets_service.update_cell(last_row, column_index, urls, sheet_name)
                            logger.info(f"Updated {media_field} for row {last_row} with {len(urls)} URLs")

            user_manager.set_user_state(chat_id, UserState.IDLE)
            media_count = user_manager.get_user_media_count(chat_id)

            # Log completion
            user_nik = user_manager.get_user_nik(chat_id)
            parsed_data = user_manager.get_user_parsed_data(chat_id)
            sc_number = parsed_data.get('SC', 'N/A') if parsed_data else 'N/A'

            logger.info(
                f"Completed data entry - NIK: {user_nik}, SC: {sc_number}, Kendala: {kendala_type.value}, Media: {media_count}")

            await update.message.reply_text(
                f"✅ Data berhasil disimpan lengkap dengan {media_count} media!\n\n"
                f"📊 **Ringkasan:**\n• SC: {sc_number}\n• Kendala: {kendala_type.value.upper()}\n• Media: {media_count} file",
                reply_markup=self._get_appropriate_menu(chat_id)
            )

            user_manager.clear_user_data(chat_id)

        except Exception as e:
            logger.exception(f"Error finishing data entry for chat_id {chat_id}")
            await update.message.reply_text(
                "❌ Terjadi kesalahan saat menyelesaikan data. Silakan coba lagi.",
                reply_markup=MenuKeyboards.media_menu()
            )
