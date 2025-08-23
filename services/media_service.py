import os
import asyncio
import logging
from functools import wraps
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
        try:
            # Download file from Telegram
            file = await bot.get_file(file_obj.file_id)
            file_path = f"/tmp/{file_obj.file_id}"
            await file.download_to_drive(file_path)

            # Upload to Cloudinary
            media_url = await self.upload_file(file_path, resource_type)

            # Clean up temporary file
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Temporary file removed: {file_path}")

            return media_url

        except Exception as e:
            logger.error(f"Error in download_and_upload_telegram_media: {e}")
            # Clean up on error
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
            raise

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