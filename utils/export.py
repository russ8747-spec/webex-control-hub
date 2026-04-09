"""
utils/export.py - CSV export helpers for Streamlit download buttons.
"""

import io
import csv
from datetime import datetime


def to_csv_bytes(data: list[dict], filename_prefix: str = "export") -> tuple[bytes, str]:
    """
    Convert a list of dicts to a UTF-8 CSV byte string.

    Returns:
        (bytes, filename) ready to pass to st.download_button.
    """
    if not data:
        return b"", f"{filename_prefix}_empty.csv"

    output   = io.StringIO()
    writer   = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)

    filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return output.getvalue().encode("utf-8"), filename


def flatten(record: dict, parent_key: str = "", sep: str = ".") -> dict:
    """
    Flatten a nested dict so it can be written to CSV.

    Example:
        {"owner": {"name": "Alice", "type": "PEOPLE"}}
        → {"owner.name": "Alice", "owner.type": "PEOPLE"}
    """
    items: list = []
    for k, v in record.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten(v, new_key, sep).items())
        elif isinstance(v, list):
            items.append((new_key, "; ".join(str(i) for i in v)))
        else:
            items.append((new_key, v))
    return dict(items)


def records_to_csv_bytes(
    data: list[dict],
    filename_prefix: str = "export",
    flatten_nested: bool = True,
) -> tuple[bytes, str]:
    """
    Like to_csv_bytes but flattens nested dicts first (useful for API responses).
    """
    if flatten_nested:
        data = [flatten(r) for r in data]
    return to_csv_bytes(data, filename_prefix)
