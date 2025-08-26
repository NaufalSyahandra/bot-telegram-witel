import os
from dotenv import load_dotenv
import cloudinary

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
            "CLOUDINARY_CLOUD_NAME",
            "CLOUDINARY_API_KEY",
            "CLOUDINARY_API_SECRET"
        ]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing environment variables: {missing}")

    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    # Google Sheets Configuration
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
    # Note: Individual sheet names are now managed by the constants.py file
    # Default sheets: "Kendala Teknik", "Kendala Pelanggan", "Kendala Lainnya"
    SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "config/service_account.json")

    # Rate Limiting
    RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "2"))

    # Session Management
    SESSION_CLEANUP_HOURS = int(os.getenv("SESSION_CLEANUP_HOURS", "24"))

    # Cloudinary Configuration
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Media Configuration
    MAX_MEDIA_SIZE_MB = int(os.getenv("MAX_MEDIA_SIZE_MB", "20"))
    ALLOWED_MEDIA_TYPES = os.getenv("ALLOWED_MEDIA_TYPES", "photo,video").split(",")

    @classmethod
    def setup_cloudinary(cls):
        """Setup Cloudinary configuration"""
        cloudinary.config(
            cloud_name=cls.CLOUDINARY_CLOUD_NAME,
            api_key=cls.CLOUDINARY_API_KEY,
            api_secret=cls.CLOUDINARY_API_SECRET
        )

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


# Validate environment on import
Config.validate_env()
Config.setup_cloudinary()