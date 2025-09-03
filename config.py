import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration settings for the bot"""

    # Environment validation
    @staticmethod
    def validate_env():
        """Validate required environment variables"""
        required_vars = [
            "BOT_TOKEN",
            "SPREADSHEET_ID",
            "MINIO_ENDPOINT",
            "MINIO_ACCESS_KEY",
            "MINIO_SECRET_KEY"
        ]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing environment variables: {missing}")

    # Telegram Bot Token
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    # Owner User ID
    OWNER_USER_ID = int(os.getenv("OWNER_USER_ID", 0))

    # Google Sheets
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
    SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "config/service_account.json")

    # Rate Limiting
    RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "2"))

    # Session Management
    SESSION_CLEANUP_HOURS = int(os.getenv("SESSION_CLEANUP_HOURS", "24"))

    # MinIO Configuration
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
    MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "telegram-bot-media")
    MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # Public URL for MinIO (optional)
    MINIO_PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "localhost:9000")
    MINIO_PUBLIC_URL = os.getenv("MINIO_PUBLIC_URL")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Media
    MAX_MEDIA_SIZE_MB = int(os.getenv("MAX_MEDIA_SIZE_MB", "20"))
    ALLOWED_MEDIA_TYPES = os.getenv("ALLOWED_MEDIA_TYPES", "photo,video").split(",")

    @classmethod
    def validate_config(cls):
        """Validate required configuration"""
        required_vars = [
            ("BOT_TOKEN", cls.BOT_TOKEN),
            ("SPREADSHEET_ID", cls.SPREADSHEET_ID),
            ("MINIO_ENDPOINT", cls.MINIO_ENDPOINT),
            ("MINIO_ACCESS_KEY", cls.MINIO_ACCESS_KEY),
            ("MINIO_SECRET_KEY", cls.MINIO_SECRET_KEY),
        ]

        missing_vars = [name for name, value in required_vars if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        if cls.OWNER_USER_ID == 0:
            print("WARNING: OWNER_USER_ID not set - owner features will be disabled")

        if not Path(cls.SERVICE_ACCOUNT_FILE).exists():
            raise FileNotFoundError(f"Service account file not found: {cls.SERVICE_ACCOUNT_FILE}")

        return True

    @classmethod
    def get_sheet_names(cls):
        return ["Kendala Teknik", "Kendala Pelanggan", "Kendala Lainnya"]

    @classmethod
    def validate_nik(cls, nik: str) -> bool:
        return nik.isdigit() and len(nik) == 16

    @classmethod
    def validate_name(cls, name: str) -> bool:
        return bool(re.match(r'^[a-zA-Z\s]+$', name.strip()))

    @classmethod
    def get_minio_public_url(cls, object_name: str) -> str:
        """Generate public URL for MinIO object"""
        if cls.MINIO_PUBLIC_URL:
            return f"{cls.MINIO_PUBLIC_URL}/{cls.MINIO_BUCKET_NAME}/{object_name}"
        else:
            protocol = "https" if cls.MINIO_SECURE else "http"
            return f"{protocol}://{cls.MINIO_PUBLIC_ENDPOINT}/{cls.MINIO_BUCKET_NAME}/{object_name}"


# Validate environment on import
Config.validate_env()
