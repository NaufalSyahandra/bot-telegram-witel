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
        client.session = AuthorizedSession(creds)  # ✅ pakai dari google.auth.transport.requests

        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        logger.info("Google Sheets connection established successfully (no deprecation warning)")
        return sheet
    except Exception as e:
        logger.error(f"Failed to setup Google Sheets: {e}")
        raise

sheet = setup_google_sheets()


# Constants and Enums
class UserState(Enum):
    IDLE = "idle"
    WAITING_INPUT = "waiting_input"


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


class MenuKeyboards:
    MAIN = [
        ["📝 Input Data SC"],
        ["📊 Cek Data", "❓ Bantuan"]
    ]

    BACK = [["🏠 Menu Utama"]]

    @staticmethod
    def main_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.MAIN, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def back_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.BACK, resize_keyboard=True)


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


# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    chat_id = update.effective_chat.id
    set_user_state(chat_id, UserState.IDLE)

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
        await update.message.reply_text(
            "🏠 Kembali ke menu utama",
            reply_markup=MenuKeyboards.main_menu()
        )


# Input Handler
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user text input for data entry (only in WAITING_INPUT state)"""
    chat_id = update.effective_chat.id
    current_state = get_user_state(chat_id)

    # Kalau user tidak sedang menunggu input, biarkan fallback_handler yang tangani
    if current_state != UserState.WAITING_INPUT:
        return

    # Rate limiting
    if not check_rate_limit(chat_id):
        await update.message.reply_text(Messages.RATE_LIMIT)
        return

    # Parse and validate input
    parsed_data = parse_input(update.message.text)
    validation_errors = validate_input(parsed_data)

    if validation_errors:
        error_message = "⚠️ " + "\n".join(validation_errors) + "\n\n" + Messages.INPUT_FORMAT
        await update.message.reply_text(error_message)
        return

    # Save to Google Sheets
    try:
        # Show typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # Prepare data for sheet
        row_data = [parsed_data[field] for field in EXPECTED_FIELDS]

        # Save to sheet (async)
        success = await append_to_sheet(row_data)

        if success:
            await update.message.reply_text(
                Messages.DATA_SAVED,
                reply_markup=MenuKeyboards.main_menu()
            )
            set_user_state(chat_id, UserState.IDLE)

            # Log successful data entry
            logger.info(f"Data saved for chat_id {chat_id}: SC={parsed_data.get('SC')}")

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

# Handler video (input via caption)
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_state = get_user_state(chat_id)

    # Wajib lewat menu "Input Data SC" dulu biar konsisten dgn alurmu
    if current_state != UserState.WAITING_INPUT:
        await update.message.reply_text(Messages.SELECT_INPUT_FIRST, reply_markup=MenuKeyboards.main_menu())
        return

    # Ambil caption berisi format SC/STO/…
    caption = (update.message.caption or "").strip()
    if not caption:
        await update.message.reply_text(
            "⚠️ Harap sertakan data di *caption* videomu sesuai format di bawah:\n\n" + Messages.INPUT_FORMAT,
            reply_markup=MenuKeyboards.back_menu()
        )
        return

    # Rate limit sama seperti input teks
    if not check_rate_limit(chat_id):
        await update.message.reply_text(Messages.RATE_LIMIT)
        return

    try:
        # Parse & validasi data dari caption
        parsed_data = parse_input(caption)
        validation_errors = validate_input(parsed_data)
        if validation_errors:
            error_message = "⚠️ " + "\n".join(validation_errors) + "\n\n" + Messages.INPUT_FORMAT
            await update.message.reply_text(error_message, reply_markup=MenuKeyboards.back_menu())
            return

        # Ambil file video dari Telegram
        video = update.message.video
        file = await context.bot.get_file(video.file_id)


        # Download ke memory (BytesIO)
        file_stream = io.BytesIO()
        file_stream.write(requests.get(file.file_path).content)
        file_stream.seek(0)

        # Upload ke Cloudinary (resource_type video)
        result = cloudinary.uploader.upload(
            file_stream,
            resource_type="video"
        )
        video_url = result["secure_url"]

        # Susun baris untuk Sheet: semua field + Link Video di kolom terakhir
        row_data = [parsed_data[field] for field in EXPECTED_FIELDS] + [video_url]

        # Simpan (pakai executor yang sudah kamu buat)
        success = await append_to_sheet(row_data)

        if success:
            await update.message.reply_text(
                f"✅ Data & video berhasil diupload!\n📺 Link video: {video_url}",
                reply_markup=MenuKeyboards.main_menu()
            )
            set_user_state(chat_id, UserState.IDLE)
            logger.info(f"Data+Video saved for chat_id {chat_id}: SC={parsed_data.get('SC')} URL={video_url}")

    except gspread.exceptions.APIError as e:
        logger.error(f"Google Sheets API error for chat_id {chat_id}: {e}")
        await update.message.reply_text(
            "❌ Error API Google Sheets. Silakan coba lagi dalam beberapa saat.",
            reply_markup=MenuKeyboards.back_menu()
        )
    except Exception as e:
        logger.exception(f"Unexpected error in handle_video for chat_id {chat_id}")
        await update.message.reply_text(
            "❌ Terjadi kesalahan saat upload video. Coba lagi ya.",
            reply_markup=MenuKeyboards.back_menu()
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
        menu_pattern = "^(📝 Input Data SC|📊 Cek Data|❓ Bantuan|🏠 Menu Utama)$"
        app.add_handler(MessageHandler(filters.Regex(menu_pattern), menu_handler))

        # Input handler (hanya teks yang bukan command dan bukan tombol menu)
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(menu_pattern),
            handle_input
        ))

        # Video + caption
        app.add_handler(MessageHandler(filters.VIDEO, handle_video))
        app.add_handler(MessageHandler(filters.Document.VIDEO, handle_video))

        # Fallback handler (catch-all, taruh paling akhir)
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