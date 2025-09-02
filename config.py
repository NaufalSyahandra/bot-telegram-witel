import os
import re
from pathlib import Path
from dotenv import load_dotenv
import cloudinary

# Load environment variables
load_dotenv()


class Config:
    """Configuration settings for the bot"""
    
    # Environment validation (from config lama)
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
    
    # Telegram Bot Token
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Owner User ID - SET THIS TO YOUR TELEGRAM USER ID (from config baru)
    OWNER_USER_ID = int(os.getenv("OWNER_USER_ID", 0))  # Replace with actual owner user ID
    
    # Google Sheets Configuration
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
    # Note: Individual sheet names are now managed by the constants.py file
    # Default sheets: "Kendala Teknik", "Kendala Pelanggan", "Kendala Lainnya"
    SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "config/service_account.json")
    
    # Media Upload Configuration
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
    
    # Rate limiting
    RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "2"))
    
    # Session Management (from config lama)
    SESSION_CLEANUP_HOURS = int(os.getenv("SESSION_CLEANUP_HOURS", "24"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "bot.log")
    
    # Media Configuration (from config lama)
    MAX_MEDIA_SIZE_MB = int(os.getenv("MAX_MEDIA_SIZE_MB", "20"))
    ALLOWED_MEDIA_TYPES = os.getenv("ALLOWED_MEDIA_TYPES", "photo,video").split(",")
    
    @classmethod
    def validate_config(cls):
        """Validate required configuration (from config baru)"""
        required_vars = [
            ("BOT_TOKEN", cls.BOT_TOKEN),
            ("SPREADSHEET_ID", cls.SPREADSHEET_ID),
            ("CLOUDINARY_CLOUD_NAME", cls.CLOUDINARY_CLOUD_NAME),
            ("CLOUDINARY_API_KEY", cls.CLOUDINARY_API_KEY),
            ("CLOUDINARY_API_SECRET", cls.CLOUDINARY_API_SECRET),
        ]
        
        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Make OWNER_USER_ID optional - if not set, owner features will be disabled
        if cls.OWNER_USER_ID == 0:
            print("WARNING: OWNER_USER_ID not set - owner features will be disabled")
        
        # Check if service account file exists
        if not Path(cls.SERVICE_ACCOUNT_FILE).exists():
            raise FileNotFoundError(f"Service account file not found: {cls.SERVICE_ACCOUNT_FILE}")
        
        return True
    
    @classmethod
    def setup_cloudinary(cls):
        """Setup Cloudinary configuration (from config lama)"""
        cloudinary.config(
            cloud_name=cls.CLOUDINARY_CLOUD_NAME,
            api_key=cls.CLOUDINARY_API_KEY,
            api_secret=cls.CLOUDINARY_API_SECRET
        )

    @classmethod
    def get_sheet_names(cls):
        """Get all sheet names that will be used (from config lama)"""
        return [
            "Kendala Teknik",
            "Kendala Pelanggan", 
            "Kendala Lainnya"
        ]

    @classmethod
    def validate_nik(cls, nik: str) -> bool:
        """Validate NIK format (16 digits) (from config lama)"""
        return nik.isdigit() and len(nik) == 16

    @classmethod
    def validate_name(cls, name: str) -> bool:
        """Validate name format (letters and spaces only) (from config lama)"""
        return bool(re.match(r'^[a-zA-Z\s]+$', name.strip()))


# Validate environment on import (from config lama)
Config.validate_env()
Config.setup_cloudinary()