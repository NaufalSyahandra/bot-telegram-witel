import os
import asyncio
import logging
import tempfile
import uuid
from telegram.error import TimedOut
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from minio import Minio
from minio.error import S3Error
from config import Config

logger = logging.getLogger(__name__)


def run_in_executor(func):
    """Decorator to run blocking operations in executor"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    return wrapper


class MediaService:
    """Media upload service class using MinIO"""

    def __init__(self):
        self.upload_folder = "telegram_bot_media"
        # Create temp directory based on OS
        self.temp_dir = self._get_temp_directory()
        # Initialize MinIO client
        self.minio_client = self._setup_minio_client()
        # Ensure bucket exists
        self._ensure_bucket_exists()

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

    def _setup_minio_client(self) -> Minio:
        """Setup MinIO client"""
        try:
            client = Minio(
                Config.MINIO_ENDPOINT,
                access_key=Config.MINIO_ACCESS_KEY,
                secret_key=Config.MINIO_SECRET_KEY,
                secure=Config.MINIO_SECURE
            )
            logger.info(f"MinIO client initialized for endpoint: {Config.MINIO_ENDPOINT}")
            return client
        except Exception as e:
            logger.error(f"Error setting up MinIO client: {e}")
            raise

    def _ensure_bucket_exists(self):
        """Ensure the bucket exists, create if it doesn't"""
        try:
            bucket_name = Config.MINIO_BUCKET_NAME
            if not self.minio_client.bucket_exists(bucket_name):
                self.minio_client.make_bucket(bucket_name)
                logger.info(f"Created MinIO bucket: {bucket_name}")

                # Set bucket policy for public read access (optional)
                self._set_bucket_policy(bucket_name)
            else:
                logger.info(f"MinIO bucket exists: {bucket_name}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error with bucket: {e}")
            raise

    def _set_bucket_policy(self, bucket_name: str):
        """Set bucket policy for public read access"""
        try:
            # Policy to allow public read access
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                        "Resource": f"arn:aws:s3:::{bucket_name}"
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/*"
                    }
                ]
            }

            import json
            self.minio_client.set_bucket_policy(bucket_name, json.dumps(policy))
            logger.info(f"Set public read policy for bucket: {bucket_name}")
        except Exception as e:
            logger.warning(f"Could not set bucket policy (this might be okay): {e}")

    def _generate_object_name(self, file_obj, resource_type: str) -> str:
        """Generate unique object name for file"""
        timestamp = datetime.now().strftime("%Y/%m/%d")
        unique_id = str(uuid.uuid4())[:8]
        extension = self._get_file_extension(file_obj, resource_type)

        # Create path: uploads/YYYY/MM/DD/unique_id.ext
        return f"uploads/{timestamp}/{unique_id}.{extension}"

    def _upload_to_minio_sync(self, file_path: str, object_name: str, content_type: str = None) -> str:
        """Synchronous upload file to MinIO and return URL"""
        try:
            # Detect content type if not provided
            if not content_type:
                if object_name.lower().endswith(('.jpg', '.jpeg')):
                    content_type = 'image/jpeg'
                elif object_name.lower().endswith('.png'):
                    content_type = 'image/png'
                elif object_name.lower().endswith('.webp'):
                    content_type = 'image/webp'
                elif object_name.lower().endswith('.mp4'):
                    content_type = 'video/mp4'
                elif object_name.lower().endswith('.mov'):
                    content_type = 'video/mov'
                else:
                    content_type = 'application/octet-stream'

            # Get file size
            file_size = os.path.getsize(file_path)

            # Upload file
            self.minio_client.fput_object(
                Config.MINIO_BUCKET_NAME,
                object_name,
                file_path,
                content_type=content_type
            )

            # Generate public URL
            url = Config.get_minio_public_url(object_name)
            logger.info(f"File uploaded to MinIO: {url} (Size: {file_size} bytes)")
            return url

        except S3Error as e:
            logger.error(f"S3 error uploading to MinIO: {e}")
            raise
        except Exception as e:
            logger.error(f"Error uploading to MinIO: {e}")
            raise

    async def upload_file(self, file_path: str, object_name: str, content_type: str = None) -> str:
        """Async wrapper for MinIO upload"""
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self._upload_to_minio_sync,
            file_path,
            object_name,
            content_type
        )

    async def download_and_upload_telegram_media(self, bot, file_obj, resource_type: str = "auto") -> str:
        """Download Telegram media and upload to MinIO with retry mechanism"""
        file_path = None
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # Download file from Telegram dengan retry
                logger.info(f"Attempting to download file (attempt {attempt + 1}/{max_retries})")
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

                # Generate object name and upload to MinIO
                object_name = self._generate_object_name(file_obj, resource_type)
                media_url = await self.upload_file(file_path, object_name)

                return media_url

            except TimedOut as e:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"All {max_retries} attempts failed due to timeout")
                    raise Exception(f"Failed to download file after {max_retries} attempts due to timeout")

            except Exception as e:
                logger.error(f"Error in download_and_upload_telegram_media (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
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

    def get_presigned_url(self, object_name: str, expires: timedelta = None) -> str:
        """Generate presigned URL for private access (if needed)"""
        try:
            if expires is None:
                expires = timedelta(days=7)

            url = self.minio_client.presigned_get_object(
                Config.MINIO_BUCKET_NAME,
                object_name,
                expires=expires
            )
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise

    def delete_object(self, object_name: str) -> bool:
        """Delete object from MinIO"""
        try:
            self.minio_client.remove_object(Config.MINIO_BUCKET_NAME, object_name)
            logger.info(f"Deleted object from MinIO: {object_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting object {object_name}: {e}")
            return False

    def list_objects(self, prefix: str = None) -> list:
        """List objects in bucket"""
        try:
            objects = self.minio_client.list_objects(
                Config.MINIO_BUCKET_NAME,
                prefix=prefix,
                recursive=True
            )
            return [obj.object_name for obj in objects]
        except Exception as e:
            logger.error(f"Error listing objects: {e}")
            return []

    def get_bucket_info(self) -> dict:
        """Get bucket information"""
        try:
            bucket_name = Config.MINIO_BUCKET_NAME
            exists = self.minio_client.bucket_exists(bucket_name)

            info = {
                "bucket_name": bucket_name,
                "exists": exists,
                "endpoint": Config.MINIO_ENDPOINT,
                "secure": Config.MINIO_SECURE
            }

            if exists:
                # Count objects (this might be slow for large buckets)
                try:
                    objects = list(self.minio_client.list_objects(bucket_name, recursive=True))
                    info["object_count"] = len(objects)
                except:
                    info["object_count"] = "unknown"

            return info
        except Exception as e:
            logger.error(f"Error getting bucket info: {e}")
            return {"error": str(e)}


# Global instance
media_service = MediaService()