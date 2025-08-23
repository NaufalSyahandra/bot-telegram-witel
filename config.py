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
    SHEET_NAME = os.getenv("SHEET_NAME", "Sheet1")
    SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "config/service_account.json")

    # Rate Limiting
    RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "2"))

    # Cloudinary Configuration
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

    @classmethod
    def setup_cloudinary(cls):
        """Setup Cloudinary configuration"""
        cloudinary.config(
            cloud_name=cls.CLOUDINARY_CLOUD_NAME,
            api_key=cls.CLOUDINARY_API_KEY,
            api_secret=cls.CLOUDINARY_API_SECRET
        )


# Validate environment on import
Config.validate_env()
Config.setup_cloudinary()