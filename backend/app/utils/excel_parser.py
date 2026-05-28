"""
backend/app/utils/excel_parser.py
-----------------------------------
Parse lecturer-uploaded Excel files containing student scores.

Expected Excel format (one row per student):
    Column A: Matric Number   (e.g., "CSC/2021/001")
    Column B: Student Name    (e.g., "Emeka Okafor")
    Column C: Score           (e.g., 75)

Why openpyxl instead of pandas for this?
- openpyxl works without heavy scientific dependencies
- We only need simple row reading, not complex data manipulation
- Smaller memory footprint for large files

The function returns a list of validated records or a list of errors.
The calling route decides what to do with the results.
"""

import openpyxl
from typing import List, Dict, Tuple


def parse_score_sheet(file_path: str) -> Tuple[List[Dict], List[str]]:
    """
    Parse an uploaded Excel score sheet.

    Args:
        file_path: Absolute path to the saved .xlsx file

    Returns:
        Tuple of:
            - records: List of dicts [{"matric": ..., "name": ..., "score": ...}]
            - errors:  List of error strings describing invalid rows

    The caller must still validate matric numbers against the database.
    """
    records = []
    errors = []

    try:
        workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        sheet = workbook.active
    except Exception as e:
        return [], [f"Could not open file: {str(e)}"]

    # Skip header row (row 1), start from row 2
    for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        # Skip completely empty rows
        if all(cell is None for cell in row):
            continue

        # Extract columns
        matric = row[0] if len(row) > 0 else None
        name = row[1] if len(row) > 1 else None
        score = row[2] if len(row) > 2 else None

        # ── Validation ────────────────────────────────────────────────────────
        row_errors = []

        if not matric or str(matric).strip() == "":
            row_errors.append(f"Row {row_idx}: Matric number is empty.")

        if score is None:
            row_errors.append(f"Row {row_idx}: Score is missing.")
        else:
            try:
                score = float(score)
                if not (0 <= score <= 100):
                    row_errors.append(f"Row {row_idx}: Score {score} is out of range (0–100).")
            except (ValueError, TypeError):
                row_errors.append(f"Row {row_idx}: Score '{score}' is not a valid number.")

        if row_errors:
            errors.extend(row_errors)
            continue  # Skip invalid rows, collect all errors first

        records.append({
            "matric": str(matric).strip().upper(),
            "name": str(name).strip() if name else "",
            "score": float(score),
        })

    workbook.close()
    return records, errors


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """
    Check if uploaded file has an allowed extension.

    Args:
        filename: Original filename from the upload
        allowed_extensions: Set of allowed extensions e.g. {"xlsx", "xls"}

    Returns:
        True if extension is in allowed set
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions
