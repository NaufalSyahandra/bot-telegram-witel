import re
import logging
from typing import Dict, List, Optional
from constants import (
    KendalaType,
    REQUIRED_FIELDS,
    SPREADSHEET_COLUMNS,
    MEDIA_FIELDS_WITH_TYPES,
    Messages
)

logger = logging.getLogger(__name__)


class DataProcessor:
    """Data processing utility class"""

    @staticmethod
    def parse_input(text: str, kendala_type: KendalaType) -> Dict[str, Optional[str]]:
        """Parse input text and extract field values based on kendala type"""
        data = {}

        # Get required fields for this kendala type
        required_fields = REQUIRED_FIELDS[kendala_type]

        # Parse each required field
        for field in required_fields:
            pattern = rf"{re.escape(field)}\s*:\s*(.+)"
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            data[field] = match.group(1).strip() if match else None

        logger.info(f"Parsed data for {kendala_type.value}: {data}")
        return data

    @staticmethod
    def validate_input(data: Dict[str, Optional[str]], kendala_type: KendalaType) -> List[str]:
        """Validate parsed input data"""
        errors = []

        # Get required fields for this kendala type
        required_fields = REQUIRED_FIELDS[kendala_type]

        # Check for missing required fields
        missing = [k for k in required_fields if k not in data or not data[k] or not data[k].strip()]
        if missing:
            errors.append(f"Field kosong: {', '.join(missing)}")

        # Validate SC format (should be numeric)
        sc = data.get("SC", "")
        if sc and not sc.isdigit():
            errors.append("SC harus berupa angka")

        # Validate distance format (for TAT and ODP_FULL)
        if kendala_type in [KendalaType.TAT, KendalaType.ODP_FULL]:
            jarak = data.get("Jarak", "")
            if jarak and not re.match(r'^\d+\s*m$', jarak.strip(), re.IGNORECASE):
                errors.append("Jarak harus berformat angka + 'm' (contoh: 20m)")

            # Validate Jumlah Tiang format (for TAT)
            if kendala_type == KendalaType.TAT:
                jumlah_tiang = data.get("Jumlah Tiang", "")
                if jumlah_tiang and not jumlah_tiang.isdigit():
                    errors.append("Jumlah Tiang harus berupa angka")

        logger.info(f"Validation errors for {kendala_type.value}: {errors}")
        return errors

    @staticmethod
    def prepare_sheet_data(data: Dict[str, str], kendala_type: KendalaType) -> List[str]:
        """Prepare data for spreadsheet insertion with NAN for missing fields"""
        row_data = []

        for column in SPREADSHEET_COLUMNS:
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
    def get_input_format(kendala_type: KendalaType) -> str:
        """Get appropriate input format based on kendala type"""
        if kendala_type == KendalaType.TAJ:
            return Messages.TAJ_FORMAT
        elif kendala_type == KendalaType.TAT:
            return Messages.TAT_FORMAT
        elif kendala_type == KendalaType.ODP_FULL:
            return Messages.ODP_FULL_FORMAT
        elif kendala_type == KendalaType.PELANGGAN:
            return Messages.GENERAL_FORMAT.format(kendala_type="Kendala Pelanggan")
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
        elif kendala_type == KendalaType.TAT:
            return Messages.TAT_MEDIA_PROMPT.format(
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
        else:
            return Messages.GENERAL_MEDIA_PROMPT.format(
                step=step + 1,
                total=total_steps,
                current_requirement=description
            )