import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration class"""

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

    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    # Google Sheets Configuration
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

    # NEW: Separate public URL for external access
    MINIO_PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "localhost:9000")
    MINIO_PUBLIC_URL = os.getenv("MINIO_PUBLIC_URL")  # Optional: full public base URL

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Media Configuration
    MAX_MEDIA_SIZE_MB = int(os.getenv("MAX_MEDIA_SIZE_MB", "20"))
    ALLOWED_MEDIA_TYPES = os.getenv("ALLOWED_MEDIA_TYPES", "photo,video").split(",")

    @classmethod
    def get_sheet_names(cls):
        """Get all sheet names that will be used"""
        return [
            "Kendala Teknik",
            "Kendala Pelanggan",
            "Kendala Lainnya"
        ]

    @classmethod
    def validate_nik(cls, nik: str) -> bool:
        """Validate NIK format (16 digits)"""
        return nik.isdigit() and len(nik) == 16

    @classmethod
    def validate_name(cls, name: str) -> bool:
        """Validate name format (letters and spaces only)"""
        import re
        return bool(re.match(r'^[a-zA-Z\s]+$', name.strip()))

    @classmethod
    def get_minio_public_url(cls, object_name: str) -> str:
        """Generate public URL for MinIO object - FIXED for external access"""
        if cls.MINIO_PUBLIC_URL:
            # Use explicit public URL if provided
            return f"{cls.MINIO_PUBLIC_URL}/{cls.MINIO_BUCKET_NAME}/{object_name}"
        else:
            # Use public endpoint for external access
            protocol = "https" if cls.MINIO_SECURE else "http"
            return f"{protocol}://{cls.MINIO_PUBLIC_ENDPOINT}/{cls.MINIO_BUCKET_NAME}/{object_name}"


# Validate environment on import
Config.validate_env()