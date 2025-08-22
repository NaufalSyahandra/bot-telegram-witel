import logging
import os
import re
import time
import asyncio
from functools import wraps
from enum import Enum
from collections import defaultdict
from typing import Dict, List, Optional
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
import cloudinary
import cloudinary.uploader
import io
import requests


# Load environment variables
load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)


# Environment validation
def validate_env():
    required_vars = ["BOT_TOKEN", "SPREADSHEET_ID"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing environment variables: {missing}")


validate_env()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "Sheet1")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "config/service_account.json")
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "2"))

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Google Sheets setup with modern authentication
def setup_google_sheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)

        client = gspread.Client(auth=creds)
        client.session = AuthorizedSession(creds)

        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        logger.info("Google Sheets connection established successfully")
        return sheet
    except Exception as e:
        logger.error(f"Failed to setup Google Sheets: {e}")
        raise

sheet = setup_google_sheets()


# Constants and Enums
class UserState(Enum):
    IDLE = "idle"
    WAITING_INPUT = "waiting_input"
    WAITING_PHOTO = "waiting_photo"
    WAITING_VIDEO = "waiting_video"


class Messages:
    WELCOME = """👋 Halo! Selamat datang di Bot Test.

📌 Pilih menu di bawah ini:"""

    INPUT_FORMAT = """📝 Silakan kirim data dengan format berikut:

SC: 12345
STO: ABC
Nama ODP: ODP-XYZ
Tag ODP: TAG-123
Tag Pelanggan: PEL-456
Jarak: 20m
Detail Kendala: Kabel putus di tiang 5

⚠️ Pastikan semua field diisi dengan benar!"""

    DATA_SAVED = "✅ Data berhasil disimpan ke Google Sheet!"
    COMING_SOON = "❌ Fitur cek data masih coming soon..."
    HELP_TEXT = "❓ Ketik /start untuk memulai ulang bot.\n\n📋 Bot ini membantu Anda menginput data SC ke Google Sheet dengan mudah."
    RATE_LIMIT = "⏳ Tunggu sebentar sebelum kirim data lagi."
    SELECT_INPUT_FIRST = "⚠️ Silakan pilih menu *Input Data SC* dulu sebelum mengirim data."

    REQUEST_PHOTO = "✅ Data berhasil diterima!\n\n📷 Sekarang silakan upload *foto* terkait kendala."
    REQUEST_VIDEO = "✅ Foto berhasil diupload!\n\n🎥 Sekarang silakan upload *video* terkait kendala."
    UPLOAD_COMPLETE = "✅ Semua data (teks, foto, video) berhasil disimpan ke Google Sheet!"


class MenuKeyboards:
    MAIN = [
        ["📝 Input Data SC"],
        ["📊 Cek Data", "❓ Bantuan"]
    ]

    BACK = [["🏠 Menu Utama"]]

    SKIP_PHOTO = [["⏭️ Lewati Foto"], ["🏠 Menu Utama"]]
    
    SKIP_VIDEO = [["⏭️ Lewati Video"], ["🏠 Menu Utama"]]

    @staticmethod
    def main_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.MAIN, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def back_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.BACK, resize_keyboard=True)
    
    @staticmethod
    def skip_photo_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.SKIP_PHOTO, resize_keyboard=True)
    
    @staticmethod
    def skip_video_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.SKIP_VIDEO, resize_keyboard=True)


# Expected fields for data input
EXPECTED_FIELDS = [
    "SC",
    "STO",
    "Nama ODP",
    "Tag ODP",
    "Tag Pelanggan",
    "Jarak",
    "Detail Kendala",
]

# User state management (in production, use database)
user_state: Dict[int, UserState] = {}
user_last_request: Dict[int, float] = defaultdict(float)


# Async wrapper for blocking operations
def run_in_executor(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    return wrapper


@run_in_executor
def append_to_sheet(data: List[str]) -> bool:
    """Append data to Google Sheet in executor to avoid blocking"""
    try:
        sheet.append_row(data)
        return True
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")
        raise


def parse_input(text: str) -> Dict[str, Optional[str]]:
    """Parse input text and extract field values"""
    data = {}
    for field in EXPECTED_FIELDS:
        pattern = rf"{re.escape(field)}\s*:\s*(.+)"
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        data[field] = match.group(1).strip() if match else None
    return data


def validate_input(data: Dict[str, Optional[str]]) -> List[str]:
    """Validate parsed input data"""
    errors = []

    # Check for missing fields
    missing = [k for k, v in data.items() if not v or not v.strip()]
    if missing:
        errors.append(f"Field kosong: {', '.join(missing)}")

    # Validate SC format (should be numeric)
    sc = data.get("SC", "")
    if sc and not sc.isdigit():
        errors.append("SC harus berupa angka")

    # Validate distance format
    jarak = data.get("Jarak", "")
    if jarak and not re.match(r'^\d+\s*m?$', jarak.strip(), re.IGNORECASE):
        errors.append("Jarak harus berformat angka + 'm' (contoh: 20m)")

    return errors


def get_user_state(chat_id: int) -> UserState:
    """Get user state, default to IDLE"""
    return user_state.get(chat_id, UserState.IDLE)


def set_user_state(chat_id: int, state: UserState):
    """Set user state"""
    user_state[chat_id] = state


def check_rate_limit(chat_id: int) -> bool:
    """Check if user is within rate limit"""
    now = time.time()
    if now - user_last_request[chat_id] < RATE_LIMIT_SECONDS:
        return False
    user_last_request[chat_id] = now
    return True


async def save_complete_data_to_sheet(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Save complete data (text + photo + video) to Google Sheet"""
    try:
        parsed_data = context.user_data.get("pending_data", {})
        photo_url = context.user_data.get("photo_url", "")
        video_url = context.user_data.get("video_url", "")

        # Debug log untuk memastikan data ada
        logger.info(f"Saving to sheet - chat_id: {chat_id}")
        logger.info(f"Text data: {parsed_data}")
        logger.info(f"Photo URL: '{photo_url}'")
        logger.info(f"Video URL: '{video_url}'")

        # Prepare row data according to EXPECTED_FIELDS order
        row_data = [parsed_data.get(field, "") for field in EXPECTED_FIELDS]
        
        # PERBAIKAN: Pastikan foto di kolom H dan video di kolom I
        row_data.append(photo_url)  # Kolom H - Photo URL
        row_data.append(video_url)  # Kolom I - Video URL

        logger.info(f"Final row data: {row_data}")

        success = await append_to_sheet(row_data)
        
        if success:
            logger.info(f"✅ Complete data saved successfully for chat_id {chat_id}: SC={parsed_data.get('SC')}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Error saving complete data for chat_id {chat_id}: {e}")
        return False


# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    chat_id = update.effective_chat.id
    set_user_state(chat_id, UserState.IDLE)
    context.user_data.clear()  # Clear any pending data

    await update.message.reply_text(
        Messages.WELCOME,
        reply_markup=MenuKeyboards.main_menu()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(Messages.HELP_TEXT)


# Menu Handlers
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu button selections"""
    text = update.message.text
    chat_id = update.effective_chat.id

    if text == "📝 Input Data SC":
        set_user_state(chat_id, UserState.WAITING_INPUT)
        context.user_data.clear()  # Clear any previous data
        await update.message.reply_text(
            Messages.INPUT_FORMAT,
            reply_markup=MenuKeyboards.back_menu()
        )

    elif text == "📊 Cek Data":
        set_user_state(chat_id, UserState.IDLE)
        await update.message.reply_text(
            Messages.COMING_SOON,
            reply_markup=MenuKeyboards.main_menu()
        )

    elif text == "❓ Bantuan":
        set_user_state(chat_id, UserState.IDLE)
        await update.message.reply_text(
            Messages.HELP_TEXT,
            reply_markup=MenuKeyboards.main_menu()
        )

    elif text == "🏠 Menu Utama":
        set_user_state(chat_id, UserState.IDLE)
        context.user_data.clear()  # Clear pending data when going back to main menu
        await update.message.reply_text(
            "🏠 Kembali ke menu utama",
            reply_markup=MenuKeyboards.main_menu()
        )
    
    elif text == "⏭️ Lewati Foto":
        current_state = get_user_state(chat_id)
        if current_state == UserState.WAITING_PHOTO:
            context.user_data["photo_url"] = ""  # Set empty photo URL
            set_user_state(chat_id, UserState.WAITING_VIDEO)
            await update.message.reply_text(
                Messages.REQUEST_VIDEO,
                reply_markup=MenuKeyboards.skip_video_menu()
            )
            logger.info(f"Photo skipped for chat_id {chat_id}")
    
    elif text == "⏭️ Lewati Video":
        current_state = get_user_state(chat_id)
        if current_state == UserState.WAITING_VIDEO:
            context.user_data["video_url"] = ""  # Set empty video URL
            
            # Save complete data to sheet SETELAH semua tahap selesai
            success = await save_complete_data_to_sheet(context, chat_id)
            
            if success:
                await update.message.reply_text(
                    Messages.UPLOAD_COMPLETE,
                    reply_markup=MenuKeyboards.main_menu()
                )
            else:
                await update.message.reply_text(
                    "❌ Terjadi error saat menyimpan data ke spreadsheet.",
                    reply_markup=MenuKeyboards.main_menu()
                )
            
            # Reset state and clear data
            set_user_state(chat_id, UserState.IDLE)
            context.user_data.clear()
            logger.info(f"Video skipped and all data saved for chat_id {chat_id}")


# Input Handler
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user text input for data entry (only in WAITING_INPUT state)"""
    chat_id = update.effective_chat.id
    current_state = get_user_state(chat_id)

    if current_state != UserState.WAITING_INPUT:
        return

    if not check_rate_limit(chat_id):
        await update.message.reply_text(Messages.RATE_LIMIT)
        return

    parsed_data = parse_input(update.message.text)
    validation_errors = validate_input(parsed_data)

    if validation_errors:
        error_message = "⚠️ " + "\n".join(validation_errors) + "\n\n" + Messages.INPUT_FORMAT
        await update.message.reply_text(error_message)
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
 
        # Save parsed data for later use - JANGAN simpan ke spreadsheet dulu
        context.user_data["pending_data"] = parsed_data
        context.user_data["photo_url"] = ""  # Initialize photo URL
        context.user_data["video_url"] = ""  # Initialize video URL

        # Set state to wait for photo
        set_user_state(chat_id, UserState.WAITING_PHOTO)

        await update.message.reply_text(
            Messages.REQUEST_PHOTO,
            reply_markup=MenuKeyboards.skip_photo_menu()
        )

        logger.info(f"Data text received and waiting for media, chat_id {chat_id}: SC={parsed_data.get('SC')}")

    except Exception as e:
        logger.error(f"Error while handling input for chat_id {chat_id}: {e}")
        await update.message.reply_text(
            "❌ Terjadi error saat memproses data.",
            reply_markup=MenuKeyboards.back_menu()
        )


# Photo Handler
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo upload"""
    chat_id = update.effective_chat.id
    current_state = get_user_state(chat_id)

    if current_state != UserState.WAITING_PHOTO:
        await update.message.reply_text(
            "⚠️ Silakan input data terlebih dahulu sebelum upload foto.",
            reply_markup=MenuKeyboards.main_menu()
        )
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        
        # Get the largest photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        # Download file to memory
        file_stream = io.BytesIO()
        await file.download_to_memory(file_stream)
        file_stream.seek(0)

        # Upload to Cloudinary
        result = cloudinary.uploader.upload(file_stream, resource_type="image")
        photo_url = result["secure_url"]

        # Save photo URL
        context.user_data["photo_url"] = photo_url

        # Move to waiting for video
        set_user_state(chat_id, UserState.WAITING_VIDEO)

        await update.message.reply_text(
            Messages.REQUEST_VIDEO,
            reply_markup=MenuKeyboards.skip_video_menu()
        )

        logger.info(f"✅ Photo uploaded and URL saved for chat_id {chat_id}: {photo_url}")
        logger.info(f"Current user_data: {context.user_data}")  # Debug log

    except Exception as e:
        logger.exception(f"Error uploading photo for chat_id {chat_id}")
        await update.message.reply_text(
            "❌ Gagal upload foto. Silakan coba lagi atau lewati.",
            reply_markup=MenuKeyboards.skip_photo_menu()
        )


# Video Handler
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video upload"""
    chat_id = update.effective_chat.id
    current_state = get_user_state(chat_id)

    if current_state != UserState.WAITING_VIDEO:
        await update.message.reply_text(
            "⚠️ Silakan input data dan upload foto terlebih dahulu.",
            reply_markup=MenuKeyboards.main_menu()
        )
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_video")
        
        # Get video file
        video = update.message.video or update.message.document
        file = await context.bot.get_file(video.file_id)

        # Download file to memory
        file_stream = io.BytesIO()
        await file.download_to_memory(file_stream)
        file_stream.seek(0)

        # Upload to Cloudinary
        result = cloudinary.uploader.upload(file_stream, resource_type="video")
        video_url = result["secure_url"]

        # Save video URL
        context.user_data["video_url"] = video_url
        
        logger.info(f"✅ Video uploaded and URL saved for chat_id {chat_id}: {video_url}")
        logger.info(f"Current user_data before saving: {context.user_data}")  # Debug log

        # SEKARANG baru save semua data ke spreadsheet setelah video selesai
        success = await save_complete_data_to_sheet(context, chat_id)

        if success:
            await update.message.reply_text(
                Messages.UPLOAD_COMPLETE,
                reply_markup=MenuKeyboards.main_menu()
            )
        else:
            await update.message.reply_text(
                "❌ Data berhasil diupload tetapi gagal disimpan ke spreadsheet.",
                reply_markup=MenuKeyboards.main_menu()
            )

        logger.info(f"Video uploaded and all data saved for chat_id {chat_id}: {video_url}")

        # Reset state and clear data
        set_user_state(chat_id, UserState.IDLE)
        context.user_data.clear()

    except Exception as e:
        logger.exception(f"Error uploading video for chat_id {chat_id}")
        await update.message.reply_text(
            "❌ Gagal upload video. Silakan coba lagi atau lewati.",
            reply_markup=MenuKeyboards.skip_video_menu()
        )


# Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}")


# Fallback Handler
async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unrecognized commands or messages"""
    chat_id = update.effective_chat.id
    current_state = get_user_state(chat_id)

    if current_state == UserState.WAITING_INPUT:
        await update.message.reply_text(
            "⚠️ Format data tidak dikenali. " + Messages.INPUT_FORMAT,
            reply_markup=MenuKeyboards.back_menu()
        )
    elif current_state == UserState.WAITING_PHOTO:
        await update.message.reply_text(
            "⚠️ Silakan upload foto atau lewati tahap ini.",
            reply_markup=MenuKeyboards.skip_photo_menu()
        )
    elif current_state == UserState.WAITING_VIDEO:
        await update.message.reply_text(
            "⚠️ Silakan upload video atau lewati tahap ini.",
            reply_markup=MenuKeyboards.skip_video_menu()
        )
    else:
        await update.message.reply_text(
            "❓ Perintah tidak dikenali. Gunakan menu di bawah atau ketik /start",
            reply_markup=MenuKeyboards.main_menu()
        )


def main():
    """Run the bot"""
    try:
        # Create application
        app = Application.builder().token(BOT_TOKEN).build()

        # Command handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))

        # Menu handlers (specific buttons)
        menu_pattern = "^(📝 Input Data SC|📊 Cek Data|❓ Bantuan|🏠 Menu Utama|⏭️ Lewati Foto|⏭️ Lewati Video)$"
        app.add_handler(MessageHandler(filters.Regex(menu_pattern), menu_handler))

        # Media handlers
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.VIDEO, handle_video))
        app.add_handler(MessageHandler(filters.Document.VIDEO, handle_video))

        # Input data handler (text input)
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(menu_pattern), 
            handle_input
        ))

        # Fallback handler (catch-all, place at the end)
        app.add_handler(MessageHandler(filters.ALL, fallback_handler))

        # Error handler
        app.add_error_handler(error_handler)

        # Start the bot
        logger.info("Starting bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()