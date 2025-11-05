import re
import logging
from typing import Dict, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from constants import (
    KendalaType,
    REQUIRED_FIELDS,
    MEDIA_FIELDS_WITH_TYPES,
    Messages,
    get_sheet_config
)

logger = logging.getLogger(__name__)


class DataProcessor:
    """Data processing utility class"""

    @staticmethod
    def parse_input(text: str, kendala_type: KendalaType) -> Dict[str, Optional[str]]:
        """Parse input text and extract field values based on kendala type (NIK excluded)"""
        data = {}

        # Get required fields for this kendala type (NIK will be added separately)
        required_fields = REQUIRED_FIELDS[kendala_type]

        # Parse each required field
        for field in required_fields:
            pattern = rf"{re.escape(field)}\s*:\s*(.+)"
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            data[field] = match.group(1).strip() if match else None

        # Add created_at timestamp
        data['created_at'] = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"Parsed data for {kendala_type.value}: {data}")
        return data

    @staticmethod
    def validate_input(data: Dict[str, Optional[str]], kendala_type: KendalaType) -> List[str]:
        """Validate parsed input data (NIK validation removed from user input)"""
        errors = []

        # Get required fields for this kendala type (NIK will be validated separately)
        required_fields = REQUIRED_FIELDS[kendala_type]

        # Check for missing required fields (excluding NIK)
        missing = [k for k in required_fields if k not in data or not data[k] or not data[k].strip()]
        if missing:
            errors.append(f"Field kosong: {', '.join(missing)}")

        # Validate NAMA (should not be empty and contain only letters and spaces)
        nama = data.get("Nama Pelanggan", "")
        if nama and not re.match(r'^[a-zA-Z\s]+$', nama.strip()):
            errors.append("Nama Pelanggan hanya boleh berisi huruf dan spasi")

        # Validate SC format (should be numeric)
        sc = data.get("SC", "")
        if not sc:
            errors.append("SC Tidak Boleh Kosong")

        # Validate distance format (for TAT types, ODP_FULL, and PELANGGAN_MANJA)
        if kendala_type in [KendalaType.TAT_BELUM_ACC, KendalaType.TAT_SUDAH_ACC, KendalaType.ODP_FULL,
                            KendalaType.PELANGGAN_MANJA]:
            jarak = data.get("Jarak Real", "")
            if jarak and not re.match(r'^\d+\s*m$', jarak.strip(), re.IGNORECASE):
                errors.append("Jarak Real harus berformat angka + 'm' (contoh: 20m)")

        # Validate Jumlah Tiang format (for both TAT types)
        if kendala_type in [KendalaType.TAT_BELUM_ACC, KendalaType.TAT_SUDAH_ACC]:
            jumlah_tiang = data.get("Jumlah Tiang", "")
            if jumlah_tiang and not jumlah_tiang.isdigit():
                errors.append("Jumlah Tiang harus berupa angka")

        # Validate date format for pelanggan types (optional validation)
        if kendala_type == KendalaType.PELANGGAN_MANJA:
            tanggal = data.get("Tanggal (Manja)", "")
            if tanggal and not re.match(r'^\d{4}-\d{2}-\d{2}$', tanggal.strip()):
                logger.warning(f"Date format might be incorrect for Tanggal (Manja): {tanggal}")

        if kendala_type == KendalaType.PELANGGAN_CANCEL:
            tanggal = data.get("Tanggal (Cancel)", "")
            if tanggal and not re.match(r'^\d{4}-\d{2}-\d{2}$', tanggal.strip()):
                logger.warning(f"Date format might be incorrect for Tanggal (Cancel): {tanggal}")

        logger.info(f"Validation errors for {kendala_type.value}: {errors}")
        return errors

    @staticmethod
    def prepare_sheet_data(data: Dict[str, str], kendala_type: KendalaType) -> List[str]:
        """Prepare data for spreadsheet insertion with NAN for missing fields (NIK already included)"""
        # Get the appropriate sheet config based on kendala type
        sheet_config = get_sheet_config(kendala_type)
        columns = sheet_config["columns"]

        row_data = []

        for column in columns:
            if column in data and data[column]:
                row_data.append(data[column])
            else:
                row_data.append("NAN")

        logger.info(f"Prepared sheet data for {kendala_type.value}: {len(row_data)} columns")
        return row_data

    @staticmethod
    def get_expected_media_info(kendala_type: KendalaType, step: int):
        """Get expected media info for current step"""
        media_list = MEDIA_FIELDS_WITH_TYPES.get(kendala_type, [])
        if 0 <= step < len(media_list):
            return media_list[step]  # Returns (field_name, media_type, description)
        return None

    @staticmethod
    def get_target_sheet_name(kendala_type: KendalaType) -> str:
        """Get target sheet name based on kendala type"""
        sheet_config = get_sheet_config(kendala_type)
        return sheet_config["name"]

    @staticmethod
    def get_sheet_columns(kendala_type: KendalaType) -> List[str]:
        """Get sheet columns based on kendala type"""
        sheet_config = get_sheet_config(kendala_type)
        return sheet_config["columns"]

    @staticmethod
    def get_input_format(kendala_type: KendalaType) -> str:
        """Get appropriate input format based on kendala type (NIK removed from all formats)"""
        if kendala_type == KendalaType.TAJ:
            return Messages.TAJ_FORMAT
        elif kendala_type == KendalaType.TAT_BELUM_ACC:
            return Messages.TAT_BELUM_ACC_FORMAT
        elif kendala_type == KendalaType.TAT_SUDAH_ACC:  # NEW: TAT Sudah ACC format
            return Messages.TAT_SUDAH_ACC_FORMAT
        elif kendala_type == KendalaType.ODP_FULL:
            return Messages.ODP_FULL_FORMAT
        elif kendala_type == KendalaType.PELANGGAN_MANJA:
            return Messages.PELANGGAN_MANJA_FORMAT
        elif kendala_type == KendalaType.PELANGGAN_CANCEL:
            return Messages.PELANGGAN_CANCEL_FORMAT
        elif kendala_type == KendalaType.CABUT_PASANG:
            return Messages.CABUT_PASANG_FORMAT
        else:  # LAINNYA
            return Messages.GENERAL_FORMAT.format(kendala_type="Kendala Lainnya")

    @staticmethod
    def get_media_prompt(kendala_type: KendalaType, step: int = 0) -> str:
        """Get appropriate media prompt based on kendala type and current step"""
        media_info = DataProcessor.get_expected_media_info(kendala_type, step)
        if not media_info:
            return Messages.GENERAL_MEDIA_PROMPT.format(
                step=step + 1,
                total=1,
                current_requirement="Media selesai"
            )

        field_name, media_type, description = media_info
        total_steps = len(MEDIA_FIELDS_WITH_TYPES.get(kendala_type, []))

        if kendala_type == KendalaType.TAJ:
            return Messages.TAJ_MEDIA_PROMPT.format(
                step=step + 1,
                total=total_steps,
                current_requirement=description
            )
        elif kendala_type == KendalaType.TAT_BELUM_ACC:
            return Messages.TAT_BELUM_ACC_MEDIA_PROMPT.format(
                step=step + 1,
                total=total_steps,
                current_requirement=description
            )
        elif kendala_type == KendalaType.TAT_SUDAH_ACC:  # NEW: TAT Sudah ACC media prompt
            return Messages.TAT_SUDAH_ACC_MEDIA_PROMPT.format(
                step=step + 1,
                total=total_steps,
                current_requirement=description
            )
        elif kendala_type == KendalaType.ODP_FULL:
            return Messages.ODP_FULL_MEDIA_PROMPT.format(
                step=step + 1,
                total=total_steps,
                current_requirement=description
            )
        elif kendala_type == KendalaType.PELANGGAN_MANJA:
            return Messages.PELANGGAN_MANJA_MEDIA_PROMPT.format(
                step=step + 1,
                total=total_steps,
                current_requirement=description
            )
        elif kendala_type == KendalaType.PELANGGAN_CANCEL:
            return Messages.PELANGGAN_CANCEL_MEDIA_PROMPT.format(
                step=step + 1,
                total=total_steps,
                current_requirement=description
            )
        elif kendala_type == KendalaType.CABUT_PASANG:
            return Messages.CABUT_PASANG_MEDIA_PROMPT.format(
                step=step + 1,
                total=total_steps,
                current_requirement=description
            )
        else:
            return Messages.LAINNYA_MEDIA_PROMPT.format(
                step=step + 1,
                total=total_steps,
                current_requirement=description
            )