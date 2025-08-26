import os
import asyncio
import logging
import tempfile
import platform
from functools import wraps
from pathlib import Path
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)


def run_in_executor(func):
    """Decorator to run blocking operations in executor"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    return wrapper


class MediaService:
    """Media upload service class"""

    def __init__(self):
        self.upload_folder = "telegram_bot_media"
        # Create temp directory based on OS
        self.temp_dir = self._get_temp_directory()

    def _get_temp_directory(self) -> str:
        """Get appropriate temporary directory based on OS"""
        try:
            # Use system's temp directory
            temp_dir = tempfile.gettempdir()
            
            # Create our specific temp folder
            bot_temp_dir = os.path.join(temp_dir, "telegram_bot_temp")
            os.makedirs(bot_temp_dir, exist_ok=True)
            
            logger.info(f"Using temp directory: {bot_temp_dir}")
            return bot_temp_dir
            
        except Exception as e:
            logger.error(f"Error creating temp directory: {e}")
            # Fallback to current directory
            fallback_dir = os.path.join(os.getcwd(), "temp")
            os.makedirs(fallback_dir, exist_ok=True)
            logger.info(f"Using fallback temp directory: {fallback_dir}")
            return fallback_dir

    def _upload_to_cloudinary_sync(self, file_path: str, resource_type: str = "auto") -> str:
        """Synchronous upload file to Cloudinary and return URL"""
        try:
            result = cloudinary.uploader.upload(
                file_path,
                resource_type=resource_type,
                folder=self.upload_folder,
                use_filename=True,
                unique_filename=True
            )
            url = result.get('secure_url')
            logger.info(f"File uploaded to Cloudinary: {url}")
            return url
        except Exception as e:
            logger.error(f"Error uploading to Cloudinary: {e}")
            raise

    async def upload_file(self, file_path: str, resource_type: str = "auto") -> str:
        """Async wrapper for Cloudinary upload"""
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self._upload_to_cloudinary_sync,
            file_path,
            resource_type
        )

    async def download_and_upload_telegram_media(self, bot, file_obj, resource_type: str = "auto") -> str:
        """Download Telegram media and upload to Cloudinary"""
        file_path = None
        try:
            # Download file from Telegram
            file = await bot.get_file(file_obj.file_id)
            
            # Create safe filename
            safe_filename = f"{file_obj.file_id}.{self._get_file_extension(file_obj, resource_type)}"
            file_path = os.path.join(self.temp_dir, safe_filename)
            
            # Ensure the file path is absolute and normalized
            file_path = os.path.abspath(file_path)
            
            logger.info(f"Downloading file to: {file_path}")
            
            # Download to the specified path
            await file.download_to_drive(file_path)
            
            # Verify file was downloaded
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Downloaded file not found at {file_path}")
                
            file_size = os.path.getsize(file_path)
            logger.info(f"File downloaded successfully. Size: {file_size} bytes")

            # Upload to Cloudinary
            media_url = await self.upload_file(file_path, resource_type)

            return media_url

        except Exception as e:
            logger.error(f"Error in download_and_upload_telegram_media: {e}")
            raise
        finally:
            # Clean up temporary file
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Temporary file removed: {file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to remove temporary file {file_path}: {cleanup_error}")

    def _get_file_extension(self, file_obj, resource_type: str) -> str:
        """Get appropriate file extension based on file type"""
        if hasattr(file_obj, 'mime_type') and file_obj.mime_type:
            if 'jpeg' in file_obj.mime_type or 'jpg' in file_obj.mime_type:
                return 'jpg'
            elif 'png' in file_obj.mime_type:
                return 'png'
            elif 'webp' in file_obj.mime_type:
                return 'webp'
            elif 'mp4' in file_obj.mime_type:
                return 'mp4'
            elif 'mov' in file_obj.mime_type:
                return 'mov'
        
        # Default based on resource type
        if resource_type == "video":
            return 'mp4'
        else:
            return 'jpg'

    def get_media_type_info(self, message) -> tuple:
        """Get media type information from Telegram message"""
        if message.photo:
            return message.photo[-1], "image", "photo", "Foto"
        elif message.video:
            return message.video, "video", "video", "Video"
        else:
            return None, None, None, None


# Global instance
media_service = MediaService()