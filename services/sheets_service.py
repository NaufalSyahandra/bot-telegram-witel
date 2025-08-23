import asyncio
import logging
from functools import wraps
from typing import List
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
from config import Config

logger = logging.getLogger(__name__)


def run_in_executor(func):
    """Decorator to run blocking operations in executor"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    return wrapper


class SheetsService:
    """Google Sheets service class"""

    def __init__(self):
        self.sheet = None
        self._setup_google_sheets()

    def _setup_google_sheets(self):
        """Setup Google Sheets connection with modern authentication"""
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(
                Config.SERVICE_ACCOUNT_FILE,
                scopes=scopes
            )

            client = gspread.Client(auth=creds)
            client.session = AuthorizedSession(creds)

            self.sheet = client.open_by_key(Config.SPREADSHEET_ID).worksheet(Config.SHEET_NAME)
            logger.info("Google Sheets connection established successfully")

        except Exception as e:
            logger.error(f"Failed to setup Google Sheets: {e}")
            raise

    @run_in_executor
    def append_row(self, data: List[str]) -> int:
        """Append data to Google Sheet and return row number"""
        try:
            self.sheet.append_row(data)
            last_row = len(self.sheet.get_all_values())
            logger.info(f"Data appended to row {last_row}")
            return last_row
        except Exception as e:
            logger.error(f"Error appending to sheet: {e}")
            raise

    @run_in_executor
    def update_cell(self, row_number: int, column_index: int, media_urls: List[str]) -> bool:
        """Update media URLs in specific cell"""
        try:
            media_urls_text = "\n".join(media_urls) if media_urls else "NAN"
            # +1 because gspread is 1-indexed
            self.sheet.update_cell(row_number, column_index + 1, media_urls_text)
            logger.info(f"Cell updated at row {row_number}, column {column_index + 1}")
            return True
        except Exception as e:
            logger.error(f"Error updating cell in sheet: {e}")
            raise

    def get_sheet_info(self) -> dict:
        """Get basic sheet information"""
        try:
            return {
                "title": self.sheet.title,
                "row_count": self.sheet.row_count,
                "col_count": self.sheet.col_count,
                "url": self.sheet.spreadsheet.url
            }
        except Exception as e:
            logger.error(f"Error getting sheet info: {e}")
            return {}


# Global instance
sheets_service = SheetsService()