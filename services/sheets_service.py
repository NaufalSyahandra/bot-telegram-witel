import asyncio
import logging
from functools import wraps
from typing import List, Dict
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
from config import Config
from constants import get_sheet_config, KendalaType, SHEET_CONFIGS

logger = logging.getLogger(__name__)


def run_in_executor(func):
    """Decorator to run blocking operations in executor"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    return wrapper


class SheetsService:
    """Google Sheets service class with multiple sheet support"""

    def __init__(self):
        self.sheets = {}  # Store multiple worksheet instances
        self.client = None
        self.spreadsheet = None
        self._setup_google_sheets()

    def _setup_google_sheets(self):
        """Setup Google Sheets connection with modern authentication"""
        try:
            logger.info("Setting up Google Sheets connection...")
            
            # Check if service account file exists
            import os
            if not os.path.exists(Config.SERVICE_ACCOUNT_FILE):
                raise FileNotFoundError(f"Service account file not found: {Config.SERVICE_ACCOUNT_FILE}")
            
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(
                Config.SERVICE_ACCOUNT_FILE,
                scopes=scopes
            )

            self.client = gspread.Client(auth=creds)
            self.client.session = AuthorizedSession(creds)

            # Open spreadsheet
            self.spreadsheet = self.client.open_by_key(Config.SPREADSHEET_ID)
            
            # Initialize all required sheets
            self._initialize_sheets()
            
            # Log sheet info
            sheet_info = self.get_spreadsheet_info()
            logger.info(f"Google Sheets connected successfully: {sheet_info}")

        except FileNotFoundError as e:
            logger.error(f"Service account file not found: {e}")
            raise
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"Spreadsheet not found with ID: {Config.SPREADSHEET_ID}")
            raise
        except Exception as e:
            logger.error(f"Failed to setup Google Sheets: {e}")
            raise

    def _initialize_sheets(self):
        """Initialize all required sheets (create if not exist)"""
        try:
            # Define required sheets with their configurations
            required_sheets = [
                ("Kendala Teknik", get_sheet_config(KendalaType.TAJ)["columns"]),
                ("Kendala Pelanggan", get_sheet_config(KendalaType.PELANGGAN_MANJA)["columns"]),
                ("Kendala Lainnya", get_sheet_config(KendalaType.LAINNYA)["columns"]),
                ("Teknisi", SHEET_CONFIGS["teknisi"]["columns"])  # CRITICAL: Teknisi sheet
            ]

            # Get existing sheets
            existing_sheets = {sheet.title: sheet for sheet in self.spreadsheet.worksheets()}

            for sheet_name, headers in required_sheets:
                if sheet_name in existing_sheets:
                    # Use existing sheet
                    self.sheets[sheet_name] = existing_sheets[sheet_name]
                    logger.info(f"Using existing sheet: {sheet_name}")
                    
                    # Verify and update headers if needed
                    self._verify_headers(self.sheets[sheet_name], headers)
                else:
                    # Create new sheet
                    logger.info(f"Creating new sheet: {sheet_name}")
                    worksheet = self.spreadsheet.add_worksheet(
                        title=sheet_name,
                        rows=1000,
                        cols=len(headers)
                    )
                    
                    # Add headers
                    worksheet.append_row(headers)
                    self.sheets[sheet_name] = worksheet
                    logger.info(f"Created sheet '{sheet_name}' with {len(headers)} columns")

        except Exception as e:
            logger.error(f"Error initializing sheets: {e}")
            raise

    def _verify_headers(self, worksheet, expected_headers):
        """Verify and update sheet headers if necessary"""
        try:
            current_headers = worksheet.row_values(1) if worksheet.row_count > 0 else []
            
            if current_headers != expected_headers:
                logger.info(f"Updating headers for sheet: {worksheet.title}")
                # Clear first row and set new headers
                if worksheet.row_count > 0:
                    worksheet.delete_rows(1)
                worksheet.insert_row(expected_headers, 1)
                logger.info(f"Headers updated for sheet: {worksheet.title}")
            else:
                logger.info(f"Headers are correct for sheet: {worksheet.title}")
                
        except Exception as e:
            logger.warning(f"Could not verify headers for {worksheet.title}: {e}")

    def _get_worksheet(self, sheet_name: str):
        """Get worksheet by name"""
        if sheet_name not in self.sheets:
            raise ValueError(f"Sheet '{sheet_name}' not found. Available sheets: {list(self.sheets.keys())}")
        return self.sheets[sheet_name]

    def _test_connection(self, sheet_name: str = None):
        """Test Google Sheets connection for specific sheet"""
        try:
            if sheet_name:
                worksheet = self._get_worksheet(sheet_name)
                test_value = worksheet.acell('A1').value
                logger.info(f"Connection test successful for {sheet_name}. A1 value: {test_value}")
            else:
                # Test with first available sheet
                first_sheet = next(iter(self.sheets.values()))
                test_value = first_sheet.acell('A1').value
                logger.info(f"Connection test successful. A1 value: {test_value}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    @run_in_executor
    def append_row(self, data: List[str], sheet_name: str) -> int:
        """Append data to specific Google Sheet and return row number"""
        try:
            logger.info(f"Attempting to append data to {sheet_name}: {data[:3]}... ({len(data)} columns)")
            
            # Get the specific worksheet
            worksheet = self._get_worksheet(sheet_name)
            
            # Test connection before appending
            if not self._test_connection(sheet_name):
                logger.error(f"Sheet connection test failed before append for {sheet_name}")
                raise Exception(f"Sheet connection not available for {sheet_name}")
            
            # Get current row count before appending
            current_rows = len(worksheet.get_all_values())
            logger.info(f"Sheet {sheet_name} currently has {current_rows} rows")
            
            # Append the row
            result = worksheet.append_row(data)
            logger.info(f"Append result for {sheet_name}: {result}")
            
            # Get new row count
            new_row_count = len(worksheet.get_all_values())
            last_row = new_row_count
            
            logger.info(f"Data successfully appended to {sheet_name} at row {last_row}")
            
            # Verify data was actually written
            if last_row > current_rows:
                written_data = worksheet.row_values(last_row)
                logger.info(f"Verification: {sheet_name} row {last_row} contains {len(written_data)} columns")
                logger.debug(f"Written data preview: {written_data[:5]}")
            
            return last_row
            
        except gspread.exceptions.APIError as e:
            logger.error(f"Google Sheets API error for {sheet_name}: {e}")
            logger.error(f"Error details: {e.response.text if hasattr(e, 'response') else 'No response details'}")
            raise
        except Exception as e:
            logger.error(f"Error appending to {sheet_name}: {e}")
            raise

    @run_in_executor
    def update_cell(self, row_number: int, column_index: int, media_urls: List[str], sheet_name: str) -> bool:
        """Update media URLs in specific cell of specific sheet"""
        try:
            logger.info(f"Updating cell in {sheet_name} at row {row_number}, column {column_index + 1} with {len(media_urls)} URLs")
            
            # Get the specific worksheet
            worksheet = self._get_worksheet(sheet_name)
            
            # Test connection
            if not self._test_connection(sheet_name):
                logger.error(f"Sheet connection test failed before update for {sheet_name}")
                raise Exception(f"Sheet connection not available for {sheet_name}")
            
            media_urls_text = "\n".join(media_urls) if media_urls else "NAN"
            
            # +1 because gspread is 1-indexed
            worksheet.update_cell(row_number, column_index + 1, media_urls_text)
            
            logger.info(f"Cell successfully updated in {sheet_name} at row {row_number}, column {column_index + 1}")
            logger.debug(f"Updated with content: {media_urls_text[:100]}...")
            
            # Verify update
            updated_value = worksheet.cell(row_number, column_index + 1).value
            logger.debug(f"Verification: Cell now contains: {updated_value[:100] if updated_value else 'None'}...")
            
            return True
            
        except gspread.exceptions.APIError as e:
            logger.error(f"Google Sheets API error during update for {sheet_name}: {e}")
            logger.error(f"Error details: {e.response.text if hasattr(e, 'response') else 'No response details'}")
            raise
        except Exception as e:
            logger.error(f"Error updating cell in {sheet_name}: {e}")
            raise

    @run_in_executor
    def get_all_teknisi_data(self) -> List[Dict]:
        """Get all teknisi data from Teknisi sheet"""
        try:
            worksheet = self._get_worksheet("Teknisi")
            all_values = worksheet.get_all_records()
            
            # Convert to list of dictionaries for easier processing
            teknisi_list = []
            for record in all_values:
                if record.get('NIK'):  # Only include records with NIK
                    teknisi_list.append({
                        'nik': str(record.get('NIK', '')),
                        'user_id': int(record.get('User_ID', 0)) if record.get('User_ID') else None,
                        'username': record.get('Username', ''),
                        'role': record.get('Role', 'employee').lower(),
                        'status': record.get('Status', 'approved').lower(),
                        'approved_by': record.get('Approved_By', ''),
                        'approved_at': record.get('Approved_At', ''),
                        'created_at': record.get('Created_At', '')
                    })
            
            logger.info(f"Retrieved {len(teknisi_list)} teknisi records from sheet")
            return teknisi_list
            
        except Exception as e:
            logger.error(f"Error getting teknisi data: {e}")
            return []

    @run_in_executor
    def update_teknisi_role(self, nik: str, new_role: str) -> bool:
        """Update teknisi role in Teknisi sheet"""
        try:
            worksheet = self._get_worksheet("Teknisi")
            
            # Find the row with matching NIK
            all_records = worksheet.get_all_records()
            for i, record in enumerate(all_records, start=2):  # Start from row 2 (skip header)
                if str(record.get('NIK', '')) == nik:
                    # Update role column (column D = index 4)
                    worksheet.update_cell(i, 4, new_role)
                    logger.info(f"Updated role for NIK {nik} to {new_role}")
                    return True
            
            logger.warning(f"NIK {nik} not found in Teknisi sheet for role update")
            return False
            
        except Exception as e:
            logger.error(f"Error updating teknisi role for NIK {nik}: {e}")
            return False

    @run_in_executor
    def delete_teknisi_data(self, nik: str) -> bool:
        """Delete teknisi data from Teknisi sheet"""
        try:
            worksheet = self._get_worksheet("Teknisi")
            
            # Find the row with matching NIK
            all_records = worksheet.get_all_records()
            for i, record in enumerate(all_records, start=2):  # Start from row 2 (skip header)
                if str(record.get('NIK', '')) == nik:
                    # Delete the entire row
                    worksheet.delete_rows(i)
                    logger.info(f"Deleted teknisi data for NIK {nik} from row {i}")
                    return True
            
            logger.warning(f"NIK {nik} not found in Teknisi sheet for deletion")
            return False
            
        except Exception as e:
            logger.error(f"Error deleting teknisi data for NIK {nik}: {e}")
            return False

    def get_spreadsheet_info(self) -> dict:
        """Get basic spreadsheet information"""
        try:
            if not self.spreadsheet:
                return {"error": "No spreadsheet connection"}
                
            info = {
                "title": self.spreadsheet.title,
                "url": self.spreadsheet.url,
                "spreadsheet_id": Config.SPREADSHEET_ID,
                "sheets": {}
            }
            
            # Add info for each sheet
            for sheet_name, worksheet in self.sheets.items():
                info["sheets"][sheet_name] = {
                    "title": worksheet.title,
                    "row_count": worksheet.row_count,
                    "col_count": worksheet.col_count
                }
            
            return info
        except Exception as e:
            logger.error(f"Error getting spreadsheet info: {e}")
            return {"error": str(e)}

    def get_last_few_rows(self, sheet_name: str, count: int = 5) -> List[List[str]]:
        """Get last few rows for debugging from specific sheet"""
        try:
            worksheet = self._get_worksheet(sheet_name)
            all_values = worksheet.get_all_values()
            return all_values[-count:] if all_values else []
        except Exception as e:
            logger.error(f"Error getting last rows from {sheet_name}: {e}")
            return []


# Global instance
sheets_service = SheetsService()