import os
import sqlite3
import shutil
from pathlib import Path
from typing import List, Optional

import openpyxl
import pandas as pd
import requests


class SheetProblem:
    def __init__(
        self, workbook_path: Path, db_path: Path, context: Optional[str], instruction: str, sheet_vars: List[str]
    ) -> None:
        self.workbook_path = workbook_path
        self.db_path = db_path
        self.context = context
        self.instruction = instruction
        self.sheet_vars = sheet_vars


def _download_file(url: str, save_path: Path) -> None:
    """Downloads a file from a URL and saves it locally.

    Args:
        url: The URL of the file to download.
        save_path: The path to save the downloaded file.

    Raises:
        requests.exceptions.RequestException: If the download fails.
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    except requests.exceptions.RequestException as e:
        # You might want to log the error here
        raise e


def _copy_local_file(source_path: Path, save_path: Path) -> None:
    """Copies a local file to the specified save path.

    Args:
        source_path: The path to the source file.
        save_path: The path to save the copied file.

    Raises:
        FileNotFoundError: If the source file doesn't exist.
        PermissionError: If there are permission issues copying the file.
        OSError: For other file system related errors.
    """
    try:
        shutil.copy2(source_path, save_path)
    except (FileNotFoundError, PermissionError, OSError) as e:
        raise e


def load_problem(
    workbook_path: Path, 
    db_path: Path, 
    instruction: str, 
    workbook_source: Optional[str] = None,
    is_local_file: bool = False
) -> SheetProblem:
    """
    Loads a sheet problem, downloading the workbook from URL or copying from local file.

    Args:
        workbook_path: The local path to save/load the workbook file.
        db_path: The path to the database directory.
        instruction: The instruction for the problem.
        workbook_source: The URL or local file path of the workbook.
        is_local_file: Whether the workbook_source is a local file path.

    Returns:
        A SheetProblem instance.
    """
    if workbook_source:
        if is_local_file:
            # Copy local file to the sandbox
            source_path = Path(workbook_source)
            _copy_local_file(source_path, workbook_path)
        else:
            # Download from URL
            _download_file(workbook_source, workbook_path)

    def create_database(wb_path: Path, db_path: Path) -> None:
        wb = pd.read_excel(wb_path, sheet_name=None)
        conn = sqlite3.connect(db_path)

        for sheet_name, df in wb.items():
            # add row number
            row_number_col = "row number"
            df.insert(0, row_number_col, range(1, 1 + len(df)))
            table_name = sheet_name
            if not df.empty:
                df.to_sql(table_name, conn, index=False, if_exists="replace")

    os.makedirs(db_path, exist_ok=True)
    db_path = db_path / "database.db"
    create_database(workbook_path, db_path)

    workbook = openpyxl.load_workbook(workbook_path)
    sheet_vars = workbook.sheetnames

    context = "The workbook is already loaded as `workbook` using openpyxl, you only need to load the sheet(s) you want to use manually. Besides, the workbook will be automatically saved, so you don't need to save it manually."
    return SheetProblem(
        workbook_path=workbook_path, db_path=db_path, context=context, instruction=instruction, sheet_vars=sheet_vars
    )
