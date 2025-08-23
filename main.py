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
from cloudinary.utils import cloudinary_url

# Load environment variables
load_dotenv()


# Environment validation
def validate_env():
    required_vars = ["BOT_TOKEN", "SPREADSHEET_ID", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY",
                     "CLOUDINARY_API_SECRET"]
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

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

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
    KENDALA_MENU = "kendala_menu"
    TEKNIK_SUBMENU = "teknik_submenu"
    WAITING_MEDIA = "waiting_media"


class KendalaType(Enum):
    TAJ = "taj"  # Tidak ada Jaringan
    TAT = "tat"  # Tidak ada Tiang
    ODP_FULL = "odp_full"
    PELANGGAN = "pelanggan"
    LAINNYA = "lainnya"


class Messages:
    WELCOME = """👋 Halo! Selamat datang di Bot Test.

📌 Pilih jenis kendala di bawah ini:"""

    KENDALA_MENU = """📋 Pilih jenis kendala:"""

    TEKNIK_SUBMENU = """🔧 Pilih kendala teknik:"""

    # Format TAJ
    TAJ_FORMAT = """📝 Silakan kirim data dengan format berikut:

SC: 12345
STO: ABC
Tag Pelanggan: PEL-456
Detail Kendala: Tidak ada Jaringan (TAJ)

⚠️ Pastikan semua field diisi dengan benar!"""

    # Format TAT
    TAT_FORMAT = """📝 Silakan kirim data dengan format berikut:

SC: 12345
STO: ABC
Nama ODP: ODP-XYZ
ID Valins: VAL-123
Tag Pelanggan: PEL-456
Jumlah Tiang: 5
Jarak: 20m
Detail Kendala: Tidak ada Tiang (TAT)
CP RT/RW/Developer: Pak RT 081234567890

⚠️ Pastikan semua field diisi dengan benar!"""

    # Format ODP Full
    ODP_FULL_FORMAT = """📝 Silakan kirim data dengan format berikut:

SC: 12345
STO: ABC
Nama ODP: ODP-XYZ
ID Valins: VAL-123
Tag Pelanggan: PEL-456
Jarak: 20m
Detail Kendala: ODP Full

⚠️ Pastikan semua field diisi dengan benar!"""

    # Format Pelanggan dan Lainnya
    GENERAL_FORMAT = """📝 Silakan kirim data dengan format berikut:

SC: 12345
STO: ABC
Tag Pelanggan: PEL-456
Detail Kendala: {kendala_type}

⚠️ Pastikan semua field diisi dengan benar!"""

    # Media prompts for different kendala types with step-by-step
    TAJ_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan
2. 🎥 Video kondisi rumah pelanggan

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    TAT_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan
2. 📸 Foto rencana pemasangan tiang
3. 📸 Bukti sudah menyerahkan file untuk sitac
4. 🎥 Video kondisi rumah pelanggan

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    ODP_FULL_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi secara berurutan!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan
2. 📸 Capture lensa nearest ODP dimana masih dalam range 250m

⚠️ Kirim sesuai urutan! Jika salah jenis media akan ditolak."""

    GENERAL_MEDIA_PROMPT = """📸 **WAJIB**: Kirim media dokumentasi!

🔸 **Langkah {step} dari {total}**: {current_requirement}

✅ Yang harus dikirim:
1. 📸 Foto dengan pelanggan/foto rumah pelanggan

⚠️ Kirim foto sesuai permintaan!"""

    MEDIA_RECEIVED = """✅ Media diterima ({media_count} file)!

📸 Anda masih bisa mengirim foto/video lainnya, atau klik 'Selesai' jika sudah lengkap."""

    DATA_SAVED = "✅ Data berhasil disimpan ke Google Sheet!"
    MEDIA_SAVED = "✅ Media berhasil diupload! ({media_type})"
    MEDIA_ERROR = "❌ Gagal mengupload media. Silakan coba lagi."
    MEDIA_REQUIRED = "⚠️ Anda harus mengirim minimal 1 foto atau video sebelum menyelesaikan input data!"
    HELP_TEXT = "❓ Ketik /start untuk memulai ulang bot.\n\n📋 Bot ini membantu Anda menginput data SC ke Google Sheet dengan mudah."
    RATE_LIMIT = "⏳ Tunggu sebentar sebelum kirim data lagi."


class MenuKeyboards:
    MAIN = [
        ["🔧 Kendala Teknik", "👤 Kendala Pelanggan"],
        ["❓ Kendala Lainnya", "🆘 Bantuan"]
    ]

    TEKNIK = [
        ["📶 Tidak ada Jaringan (TAJ)"],
        ["🏗️ Tidak ada Tiang (TAT)"],
        ["🔌 ODP Full"],
        ["🏠 Menu Utama"]
    ]

    BACK = [["🏠 Menu Utama"]]

    MEDIA_OPTIONS = [
        ["✅ Selesai"],
        ["🏠 Menu Utama"]
    ]

    @staticmethod
    def main_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.MAIN, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def teknik_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.TEKNIK, resize_keyboard=True, one_time_keyboard=False)

    @staticmethod
    def back_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.BACK, resize_keyboard=True)

    @staticmethod
    def media_menu():
        return ReplyKeyboardMarkup(MenuKeyboards.MEDIA_OPTIONS, resize_keyboard=True)


# Spreadsheet columns - URUTAN PENTING SESUAI HEADER
SPREADSHEET_COLUMNS = [
    "SC",
    "STO",
    "Detail Kendala",
    "Tag Pelanggan",
    "Nama ODP",
    "ID Valins",
    "Jarak",
    "Jumlah Tiang",
    "Foto dengan Pelanggan/Foto Rumah Pelanggan",
    "Foto Rencana Pemasangan Tiang",
    "Video Kondisi Rumah Pelanggan",
    "Bukti Sudah Menyerahkan File untuk Sitac",
    "Capture Lensa Nearest ODP dimana Masih dalam Range 250m"
]

# Define which fields are required for each kendala type
REQUIRED_FIELDS = {
    KendalaType.TAJ: ["SC", "STO", "Tag Pelanggan", "Detail Kendala"],
    KendalaType.TAT: ["SC", "STO", "Nama ODP", "ID Valins", "Tag Pelanggan", "Jumlah Tiang", "Jarak", "Detail Kendala",
                      "CP RT/RW/Developer"],
    KendalaType.ODP_FULL: ["SC", "STO", "Nama ODP", "ID Valins", "Tag Pelanggan", "Jarak", "Detail Kendala"],
    KendalaType.PELANGGAN: ["SC", "STO", "Tag Pelanggan", "Detail Kendala"],
    KendalaType.LAINNYA: ["SC", "STO", "Tag Pelanggan", "Detail Kendala"]
}

# Define media fields for each kendala type with expected media types
MEDIA_FIELDS_WITH_TYPES = {
    KendalaType.TAJ: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan"),
        ("Video Kondisi Rumah Pelanggan", "video", "🎥 Video kondisi rumah pelanggan")
    ],
    KendalaType.TAT: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan"),
        ("Foto Rencana Pemasangan Tiang", "photo", "📸 Foto rencana pemasangan tiang"),
        ("Bukti Sudah Menyerahkan File untuk Sitac", "photo", "📸 Bukti sudah menyerahkan file untuk sitac"),
        ("Video Kondisi Rumah Pelanggan", "video", "🎥 Video kondisi rumah pelanggan")
    ],
    KendalaType.ODP_FULL: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan"),
        ("Capture Lensa Nearest ODP dimana Masih dalam Range 250m", "photo",
         "📸 Capture lensa nearest ODP dimana masih dalam range 250m")
    ],
    KendalaType.PELANGGAN: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan")
    ],
    KendalaType.LAINNYA: [
        ("Foto dengan Pelanggan/Foto Rumah Pelanggan", "photo", "📸 Foto dengan pelanggan/foto rumah pelanggan")
    ]
}

# Legacy media fields (for backward compatibility)
MEDIA_FIELDS = {
    kendala_type: [item[0] for item in fields]
    for kendala_type, fields in MEDIA_FIELDS_WITH_TYPES.items()
}

# User state management (in production, use database)
user_state: Dict[int, UserState] = {}
user_last_request: Dict[int, float] = defaultdict(float)
user_kendala_type: Dict[int, KendalaType] = {}
user_last_row: Dict[int, int] = {}
user_media_urls: Dict[int, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))  # Store URLs by media type
user_media_count: Dict[int, int] = defaultdict(int)
user_parsed_data: Dict[int, Dict[str, str]] = {}  # Store parsed user data
user_media_step: Dict[int, int] = defaultdict(int)  # Track current media step for each user


# Async wrapper for blocking operations
def run_in_executor(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    return wrapper


@run_in_executor
def append_to_sheet(data: List[str]) -> int:
    """Append data to Google Sheet in executor to avoid blocking"""
    try:
        sheet.append_row(data)
        last_row = len(sheet.get_all_values())
        return last_row
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")
        raise


@run_in_executor
def update_media_in_sheet(row_number: int, column_index: int, media_urls: List[str]) -> bool:
    """Update media URLs in specific cell"""
    try:
        media_urls_text = "\n".join(media_urls) if media_urls else "NAN"
        sheet.update_cell(row_number, column_index + 1, media_urls_text)  # +1 because gspread is 1-indexed
        return True
    except Exception as e:
        logger.error(f"Error updating media in sheet: {e}")
        raise


def upload_to_cloudinary_sync(file_path: str, resource_type: str = "auto") -> str:
    """Synchronous upload file to Cloudinary and return URL"""
    try:
        result = cloudinary.uploader.upload(
            file_path,
            resource_type=resource_type,
            folder="telegram_bot_media",
            use_filename=True,
            unique_filename=True
        )
        return result.get('secure_url')
    except Exception as e:
        logger.error(f"Error uploading to Cloudinary: {e}")
        raise


async def upload_to_cloudinary(file_path: str, resource_type: str = "auto") -> str:
    """Async wrapper for Cloudinary upload"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, upload_to_cloudinary_sync, file_path, resource_type)


def parse_input(text: str, kendala_type: KendalaType) -> Dict[str, Optional[str]]:
    """Parse input text and extract field values based on kendala type"""
    data = {}

    # Get required fields for this kendala type
    required_fields = REQUIRED_FIELDS[kendala_type]

    # Parse each required field
    for field in required_fields:
        pattern = rf"{re.escape(field)}\s*:\s*(.+)"
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        data[field] = match.group(1).strip() if match else None

    return data


def validate_input(data: Dict[str, Optional[str]], kendala_type: KendalaType) -> List[str]:
    """Validate parsed input data"""
    errors = []

    # Get required fields for this kendala type
    required_fields = REQUIRED_FIELDS[kendala_type]

    # Check for missing required fields
    missing = [k for k in required_fields if k not in data or not data[k] or not data[k].strip()]
    if missing:
        errors.append(f"Field kosong: {', '.join(missing)}")

    # Validate SC format (should be numeric)
    sc = data.get("SC", "")
    if sc and not sc.isdigit():
        errors.append("SC harus berupa angka")

    # Validate distance format (for TAT and ODP_FULL)
    if kendala_type in [KendalaType.TAT, KendalaType.ODP_FULL]:
        jarak = data.get("Jarak", "")
        if jarak and not re.match(r'^\d+\s*m?$', jarak.strip(), re.IGNORECASE):
            errors.append("Jarak harus berformat angka + 'm' (contoh: 20m)")

    # Validate Jumlah Tiang format (for TAT)
    if kendala_type == KendalaType.TAT:
        jumlah_tiang = data.get("Jumlah Tiang", "")
        if jumlah_tiang and not jumlah_tiang.isdigit():
            errors.append("Jumlah Tiang harus berupa angka")

    return errors


def prepare_sheet_data(data: Dict[str, str], kendala_type: KendalaType) -> List[str]:
    """Prepare data for spreadsheet insertion with NAN for missing fields"""
    row_data = []

    for column in SPREADSHEET_COLUMNS:
        if column in data and data[column]:
            row_data.append(data[column])
        else:
            row_data.append("NAN")

    return row_data


def get_user_state(chat_id: int) -> UserState:
    return user_state.get(chat_id, UserState.IDLE)


def set_user_state(chat_id: int, state: UserState):
    user_state[chat_id] = state


def get_user_kendala_type(chat_id: int) -> Optional[KendalaType]:
    return user_kendala_type.get(chat_id)


def set_user_kendala_type(chat_id: int, kendala_type: KendalaType):
    user_kendala_type[chat_id] = kendala_type


def get_user_last_row(chat_id: int) -> int:
    return user_last_row.get(chat_id, 0)


def set_user_last_row(chat_id: int, row_number: int):
    user_last_row[chat_id] = row_number


def get_user_media_urls(chat_id: int) -> Dict[str, List[str]]:
    return user_media_urls.get(chat_id, defaultdict(list))


def add_user_media_url(chat_id: int, media_type: str, url: str):
    user_media_urls[chat_id][media_type].append(url)
    user_media_count[chat_id] += 1


def get_user_media_step(chat_id: int) -> int:
    """Get current media step for user"""
    return user_media_step.get(chat_id, 0)


def set_user_media_step(chat_id: int, step: int):
    """Set current media step for user"""
    user_media_step[chat_id] = step


def increment_user_media_step(chat_id: int):
    """Increment user media step"""
    old_step = user_media_step.get(chat_id, 0)
    user_media_step[chat_id] = old_step + 1
    logger.info(f"Media step incremented for chat_id {chat_id}: {old_step} -> {user_media_step[chat_id]}")


def get_user_media_count(chat_id: int) -> int:
    return user_media_count.get(chat_id, 0)


def get_expected_media_info(kendala_type: KendalaType, step: int):
    """Get expected media info for current step"""
    media_list = MEDIA_FIELDS_WITH_TYPES.get(kendala_type, [])
    if 0 <= step < len(media_list):
        return media_list[step]  # Returns (field_name, media_type, description)
    return None


def get_user_parsed_data(chat_id: int) -> Dict[str, str]:
    return user_parsed_data.get(chat_id, {})


def set_user_parsed_data(chat_id: int, data: Dict[str, str]):
    user_parsed_data[chat_id] = data


def clear_user_data(chat_id: int):
    """Clear all user data"""
    logger.info(f"Clearing user data for chat_id {chat_id}")
    user_kendala_type.pop(chat_id, None)
    user_last_row.pop(chat_id, None)
    user_media_urls.pop(chat_id, None)
    user_media_count.pop(chat_id, None)
    user_parsed_data.pop(chat_id, None)
    user_media_step.pop(chat_id, None)


def check_rate_limit(chat_id: int) -> bool:
    now = time.time()
    if now - user_last_request[chat_id] < RATE_LIMIT_SECONDS:
        return False
    user_last_request[chat_id] = now
    return True


def debug_user_state(chat_id: int):
    """Debug function to log user state"""
    logger.info(f"DEBUG - User {chat_id} state:")
    logger.info(f"  - State: {get_user_state(chat_id)}")
    logger.info(f"  - Kendala type: {get_user_kendala_type(chat_id)}")
    logger.info(f"  - Media step: {get_user_media_step(chat_id)}")
    logger.info(f"  - Media count: {get_user_media_count(chat_id)}")
    logger.info(f"  - Media URLs: {get_user_media_urls(chat_id)}")


def get_media_prompt(kendala_type: KendalaType, step: int = 0) -> str:
    """Get appropriate media prompt based on kendala type and current step"""
    media_info = get_expected_media_info(kendala_type, step)
    if not media_info:
        return Messages.GENERAL_MEDIA_PROMPT.format(step=step + 1, total=1, current_requirement="Media selesai")

    field_name, media_type, description = media_info
    total_steps = len(MEDIA_FIELDS_WITH_TYPES.get(kendala_type, []))

    if kendala_type == KendalaType.TAJ:
        return Messages.TAJ_MEDIA_PROMPT.format(
            step=step + 1,
            total=total_steps,
            current_requirement=description
        )
    elif kendala_type == KendalaType.TAT:
        return Messages.TAT_MEDIA_PROMPT.format(
            step=step + 1,
            total=total_steps,
            current_requirement=description
        )
    elif kendala_type == KendalaType.ODP_FULL:
        return Messages.ODP_FULL_MEDIA_PROMPT.format(
            step=step + 1,
            total=total_steps,
            current_requirement=description
        )
    else:
        return Messages.GENERAL_MEDIA_PROMPT.format(
            step=step + 1,
            total=total_steps,
            current_requirement=description
        )


def get_input_format(kendala_type: KendalaType) -> str:
    """Get appropriate input format based on kendala type"""
    if kendala_type == KendalaType.TAJ:
        return Messages.TAJ_FORMAT
    elif kendala_type == KendalaType.TAT:
        return Messages.TAT_FORMAT
    elif kendala_type == KendalaType.ODP_FULL:
        return Messages.ODP_FULL_FORMAT
    elif kendala_type == KendalaType.PELANGGAN:
        return Messages.GENERAL_FORMAT.format(kendala_type="Kendala Pelanggan")
    else:  # LAINNYA
        return Messages.GENERAL_FORMAT.format(kendala_type="Kendala Lainnya")


# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    set_user_state(chat_id, UserState.IDLE)
    clear_user_data(chat_id)

    await update.message.reply_text(
        Messages.WELCOME,
        reply_markup=MenuKeyboards.main_menu()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(Messages.HELP_TEXT)


# FIXED Media Handler
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_state = get_user_state(chat_id)

    # Debug logging
    debug_user_state(chat_id)

    if current_state != UserState.WAITING_MEDIA:
        return

    if not check_rate_limit(chat_id):
        await update.message.reply_text(Messages.RATE_LIMIT)
        return

    kendala_type = get_user_kendala_type(chat_id)
    if not kendala_type:
        await update.message.reply_text("❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start")
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")

        # Determine media type from message
        actual_media_type = None
        file_obj = None
        resource_type = None
        media_type_name = None

        if update.message.photo:
            file_obj = update.message.photo[-1]
            resource_type = "image"
            actual_media_type = "photo"
            media_type_name = "Foto"
        elif update.message.video:
            file_obj = update.message.video
            resource_type = "video"
            actual_media_type = "video"
            media_type_name = "Video"
        else:
            await update.message.reply_text("❌ Hanya foto dan video yang diterima!")
            return

        # Get current step and expected media
        current_step = get_user_media_step(chat_id)
        expected_media_info = get_expected_media_info(kendala_type, current_step)

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

        # Download file
        file = await context.bot.get_file(file_obj.file_id)
        file_path = f"/tmp/{file_obj.file_id}"
        await file.download_to_drive(file_path)

        # Upload to Cloudinary
        media_url = await upload_to_cloudinary(file_path, resource_type)

        # Add media URL to the correct field for current step
        add_user_media_url(chat_id, field_name, media_url)

        # Increment step after successful upload
        increment_user_media_step(chat_id)

        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

        # Check if we need more media
        new_step = get_user_media_step(chat_id)
        total_required = len(MEDIA_FIELDS_WITH_TYPES.get(kendala_type, []))

        if new_step < total_required:
            # Show next required media
            next_media_info = get_expected_media_info(kendala_type, new_step)
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
            media_count = get_user_media_count(chat_id)
            await update.message.reply_text(
                f"✅ Semua media berhasil diterima ({media_count} file)!\n\n"
                f"Klik 'Selesai' untuk menyelesaikan input data.",
                reply_markup=MenuKeyboards.media_menu()
            )

        logger.info(f"Media step {current_step} completed for chat_id {chat_id}: {media_url} (Type: {media_type_name})")

    except Exception as e:
        logger.exception(f"Error handling media for chat_id {chat_id}")
        await update.message.reply_text(
            Messages.MEDIA_ERROR,
            reply_markup=MenuKeyboards.media_menu()
        )


# Menu Handlers
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    # Main menu options
    if text == "🔧 Kendala Teknik":
        set_user_state(chat_id, UserState.TEKNIK_SUBMENU)
        await update.message.reply_text(
            Messages.TEKNIK_SUBMENU,
            reply_markup=MenuKeyboards.teknik_menu()
        )

    elif text == "👤 Kendala Pelanggan":
        set_user_kendala_type(chat_id, KendalaType.PELANGGAN)
        set_user_state(chat_id, UserState.WAITING_INPUT)
        await update.message.reply_text(
            get_input_format(KendalaType.PELANGGAN),
            reply_markup=MenuKeyboards.back_menu()
        )

    elif text == "❓ Kendala Lainnya":
        set_user_kendala_type(chat_id, KendalaType.LAINNYA)
        set_user_state(chat_id, UserState.WAITING_INPUT)
        await update.message.reply_text(
            get_input_format(KendalaType.LAINNYA),
            reply_markup=MenuKeyboards.back_menu()
        )

    elif text == "🆘 Bantuan":
        set_user_state(chat_id, UserState.IDLE)
        await update.message.reply_text(
            Messages.HELP_TEXT,
            reply_markup=MenuKeyboards.main_menu()
        )

    # Teknik submenu options
    elif text == "📶 Tidak ada Jaringan (TAJ)":
        set_user_kendala_type(chat_id, KendalaType.TAJ)
        set_user_state(chat_id, UserState.WAITING_INPUT)
        await update.message.reply_text(
            get_input_format(KendalaType.TAJ),
            reply_markup=MenuKeyboards.back_menu()
        )

    elif text == "🏗️ Tidak ada Tiang (TAT)":
        set_user_kendala_type(chat_id, KendalaType.TAT)
        set_user_state(chat_id, UserState.WAITING_INPUT)
        await update.message.reply_text(
            get_input_format(KendalaType.TAT),
            reply_markup=MenuKeyboards.back_menu()
        )

    elif text == "🔌 ODP Full":
        set_user_kendala_type(chat_id, KendalaType.ODP_FULL)
        set_user_state(chat_id, UserState.WAITING_INPUT)
        await update.message.reply_text(
            get_input_format(KendalaType.ODP_FULL),
            reply_markup=MenuKeyboards.back_menu()
        )

    # FIXED Media menu options - "✅ Selesai"
    elif text == "✅ Selesai":
        kendala_type = get_user_kendala_type(chat_id)
        if not kendala_type:
            await update.message.reply_text("❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start")
            return

        current_step = get_user_media_step(chat_id)
        total_required = len(MEDIA_FIELDS_WITH_TYPES.get(kendala_type, []))

        # Check if all required media have been uploaded
        if current_step < total_required:
            # Show what's missing
            next_media_info = get_expected_media_info(kendala_type, current_step)
            if next_media_info:
                field_name, expected_type, description = next_media_info
                expected_name = "Foto" if expected_type == "photo" else "Video"

                # Show remaining requirements
                remaining_media = []
                for i in range(current_step, total_required):
                    media_info = get_expected_media_info(kendala_type, i)
                    if media_info:
                        _, media_type, desc = media_info
                        type_name = "📸 Foto" if media_type == "photo" else "🎥 Video"
                        remaining_media.append(f"{i + 1}. {type_name}: {desc}")

                await update.message.reply_text(
                    f"⚠️ Masih ada media yang belum dikirim:\n\n" +
                    "\n".join(remaining_media) +
                    f"\n\n🔸 **Selanjutnya kirim**: {expected_name} - {description}",
                    reply_markup=MenuKeyboards.media_menu()
                )
                return

        # All media completed - proceed with saving
        try:
            last_row = get_user_last_row(chat_id)
            media_urls_dict = get_user_media_urls(chat_id)

            if last_row > 0 and kendala_type:
                # Update each media column
                for media_field in MEDIA_FIELDS[kendala_type]:
                    column_index = SPREADSHEET_COLUMNS.index(media_field)
                    urls = media_urls_dict.get(media_field, [])
                    await update_media_in_sheet(last_row, column_index, urls)

            set_user_state(chat_id, UserState.IDLE)
            media_count = get_user_media_count(chat_id)
            await update.message.reply_text(
                f"✅ Data berhasil disimpan lengkap dengan {media_count} media!",
                reply_markup=MenuKeyboards.main_menu()
            )

            clear_user_data(chat_id)

        except Exception as e:
            logger.exception(f"Error finishing data entry for chat_id {chat_id}")
            await update.message.reply_text(
                "❌ Terjadi kesalahan saat menyelesaikan data. Silakan coba lagi.",
                reply_markup=MenuKeyboards.media_menu()
            )

    # Navigation
    elif text == "🏠 Menu Utama":
        set_user_state(chat_id, UserState.IDLE)
        await update.message.reply_text(
            "🏠 Kembali ke menu utama",
            reply_markup=MenuKeyboards.main_menu()
        )
        clear_user_data(chat_id)


# Input Handler
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_state = get_user_state(chat_id)

    if current_state != UserState.WAITING_INPUT:
        return

    if not check_rate_limit(chat_id):
        await update.message.reply_text(Messages.RATE_LIMIT)
        return

    kendala_type = get_user_kendala_type(chat_id)
    if not kendala_type:
        await update.message.reply_text("❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start")
        return

    # Parse and validate input
    parsed_data = parse_input(update.message.text, kendala_type)
    validation_errors = validate_input(parsed_data, kendala_type)

    if validation_errors:
        error_message = "⚠️ " + "\n".join(validation_errors) + "\n\n" + get_input_format(kendala_type)
        await update.message.reply_text(error_message)
        return

    # Store parsed data for later use
    set_user_parsed_data(chat_id, parsed_data)

    # Save to Google Sheets
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # Prepare data for sheet with NAN for missing fields
        row_data = prepare_sheet_data(parsed_data, kendala_type)

        # Save to sheet (async)
        last_row = await append_to_sheet(row_data)
        set_user_last_row(chat_id, last_row)

        if last_row > 0:
            # Change state to waiting for media
            set_user_state(chat_id, UserState.WAITING_MEDIA)
            set_user_media_step(chat_id, 0)  # Start from step 0

            logger.info(f"Starting media collection for chat_id {chat_id}, kendala_type: {kendala_type.value}")

            await update.message.reply_text(
                get_media_prompt(kendala_type, 0),
                reply_markup=MenuKeyboards.media_menu(),
                parse_mode='Markdown'
            )

            # Log successful data entry
            logger.info(f"Data saved for chat_id {chat_id}: SC={parsed_data.get('SC')}, Kendala={kendala_type.value}")

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
        kendala_type = get_user_kendala_type(chat_id)
        if kendala_type:
            await update.message.reply_text(
                "⚠️ Format data tidak dikenali. " + get_input_format(kendala_type),
                reply_markup=MenuKeyboards.back_menu()
            )
        else:
            await update.message.reply_text(
                "❌ Error: Jenis kendala tidak ditemukan. Silakan mulai ulang dengan /start",
                reply_markup=MenuKeyboards.main_menu()
            )
    elif current_state == UserState.WAITING_MEDIA:
        kendala_type = get_user_kendala_type(chat_id)
        if kendala_type:
            current_step = get_user_media_step(chat_id)
            expected_media_info = get_expected_media_info(kendala_type, current_step)
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


def main():
    """Run the bot"""
    try:
        # Create application
        app = Application.builder().token(BOT_TOKEN).build()

        # Command handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))

        # Menu handlers (specific buttons)
        menu_pattern = "^(🔧 Kendala Teknik|👤 Kendala Pelanggan|❓ Kendala Lainnya|🆘 Bantuan|📶 Tidak ada Jaringan \\(TAJ\\)|🏗️ Tidak ada Tiang \\(TAT\\)|🔌 ODP Full|🏠 Menu Utama|✅ Selesai)$"
        app.add_handler(MessageHandler(filters.Regex(menu_pattern), menu_handler))

        # Media handlers (photo and video)
        app.add_handler(MessageHandler(filters.PHOTO, handle_media))
        app.add_handler(MessageHandler(filters.VIDEO, handle_media))

        # Input handler (hanya teks yang bukan command dan bukan tombol menu)
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(menu_pattern),
            handle_input
        ))

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