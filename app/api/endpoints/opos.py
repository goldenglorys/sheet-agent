import logging
from datetime import datetime
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl, Field, field_validator

from app.services.analysis_service import run_analysis

router = APIRouter()
PROMPT = f"""
You have to analyze an open posts list from a company. It holds all unpaid invoices and credits for the company.
            
            # Rules
            - Check the format of the due date in the excel file. Chances are high that the format used is german. You need to cater for this.
            - Identify the format of "non-cumulative" rows. These are typically rows that contain an invoice number, a due date, an invoice date and an invoice amount.
            - Identify "invoice" rows. These are rows that are "non-cumulative" AND have a positive invoice amount.
            - Identify "credit" rows. These are rows that are "non-cumulative" AND have a negative invoice amount.
            - All rows that are not "non-cumulative" are "cumulative" rows. 
            - You get the maturity of an invoice by calculating the difference between today's date and the due date. 
            - You store all your output in a new sheet named "Analysis".
            
            # Your Tasks
            You provide a multi-step analysis of the entire open posts list.
            Here is each step outlined with additional instructions:
            1. Create a list of "cumulative" row numbers
               - You can tell that a row is cumulative if the key identifier (mostly the invoice number) all of a sudden changes format compared to the previous rows.
               - Sometimes, the key identifier contains the word "debitor", "debtor", "creditor". You then know that the file holds cumulative rows.
               - Sometimes, the values such as invoice date, due date, etc are empty
               - Other forms of cumulative rows are rows that accumulate the entire file under a given filter.
               - Programmatically create a list of "cumulative" row numbers.
               - Make sure to reuse the list accordingly in later steps.
            2. Create a list of "invoice" row numbers
               - You can tell that a row is an invoice row if it is not a "cumulative" row and has a POSITIVE invoice amount.
               - Programmatically create a list of "cumulative" row numbers.
               - Make sure to reuse the list accordingly in later steps.
            3. Create a list of "credit" row numbers
               - You can tell that a row is a credit row if it is not a "cumulative" row and has a NEGATIVE invoice amount.
               - Programmatically create a list of "credit" row numbers.
               - Make sure to reuse the list accordingly in later steps.
            4. Check each "invoice" and each "credit" row for completeness. "Is all required information present?"
               - Are invoice numbers, amounts, addresses, debtor names, creditor names, debtor numbers, etc present?
               - Use only "invoice" rows and "credit" rows.
            5. Calculate the sum over the invoice amounts of all "invoice" rows
            6. Calculate the sum over the credit amounts of all "credit" rows
            7. Create an ageing report on the "invoice" rows.
               - Cluster "invoice" rows by maturity into clusters: 1. Not mature 2. 1-30 days maturity 3. 31-60 days maturity 4. >60 days maturity. 
               - Calculate the maturity of a credit row by: (today's date - due date).days
               - For each maturity cluster, accumulate the invoice amount (sum of all invoice amounts in the cluster). 
               - For each maturity cluster, give the percentage of the total accumulated invoice amount, calculated in step 3.
            8. Create an ageing report on the "credit" rows.
               - Cluster "credit" rows by maturity into clusters: 1. Not mature 2. 1-30 days maturity 3. 31-60 days maturity 4. >60 days maturity. 
               - Calculate the maturity of a credit row by: (today's date - due date).days
               - For each maturity cluster, accumulate the credit amount (sum of all credit amounts in the cluster). 
               - For each maturity cluster, give the percentage of the total accumulated credit amount, calculated in step 4.
            9. Calculate the top 10 credit positions by amount (lowest to highest).
            10. Calculate the top 10 debtor positions by amount (highest to lowest).
            11. Duplicate analysis
               - Check whether the "invoice" rows hold duplicate invoice numbers.
               - If there are duplicates, provide a list of the duplicate invoice numbers.
               - Check the "cumulative" rows for duplicate debtor numbers or names.
               - If there are duplicates, provide a list of the duplicate debtor numbers or names.
            
            # Output
            Create a new sheet named "Analysis".
            Write the output in the "Analysis" sheet.
            Paste the output of each step so that it is clearly visible and easy to understand.     
            Use columns to separate the output of each step
            
            Today's date is the {datetime.now().strftime("%dth of %B %Y")}
            
            Take a deep breath and think step by step.
"""

TEST_PROMPT = """
You have to analyze an open posts list from a company. It holds all unpaid invoices and credits for the company.
            
            # Rules
            - Check the format of the due date in the excel file. Chances are high that the format used is german. You need to cater for this.
            - Identify the format of "non-cumulative" rows. These are typically rows that contain an invoice number, a due date, an invoice date and an invoice amount.
            - Identify "invoice" rows. These are rows that are "non-cumulative" AND have a positive invoice amount.
            - Identify "credit" rows. These are rows that are "non-cumulative" AND have a negative invoice amount.
            - All rows that are not "non-cumulative" are "cumulative" rows. 
            - You get the maturity of an invoice by calculating the difference between today's date and the due date. 
            - You store all your output in a new sheet named "Analysis".
            
            # Your Tasks
            You provide a multi-step analysis of the entire open posts list.
            Here is each step outlined with additional instructions:
            1. Create a list of "cumulative" row numbers
               - You can tell that a row is cumulative if the key identifier (mostly the invoice number) all of a sudden changes format compared to the previous rows.
               - Sometimes, the key identifier contains the word "debitor", "debtor", "creditor". You then know that the file holds cumulative rows.
               - Sometimes, the values such as invoice date, due date, etc are empty
               - Other forms of cumulative rows are rows that accumulate the entire file under a given filter.
               - Programmatically create a list of "cumulative" row numbers.
               - Make sure to reuse the list accordingly in later steps.
            
            
            # Output
            Write the output in the "Analysis" sheet.
            Paste the output of each step so that it is clearly visible and easy to understand.     
            Use columns to separate the output of each step
            
            Today's date is the 10th of June 2025
            
            Take a deep breath and think step by step.
"""


TEST = "Create a new sheet named 'Analysis'. Then write 'Hello World' in the sheet."


class AnalysisRequest(BaseModel):
    """Request model for the analysis endpoint."""

    instruction: str = Field(PROMPT, description="The instruction for the analysis")
    workbook_source: str = Field(
        "https://storage.googleapis.com/kritis-documents/Opos-test.xlsx",
        description="The URL or local file path of the workbook to analyze",
    )

    @field_validator("workbook_source")
    @classmethod
    def validate_workbook_source(cls, v: str) -> str:
        """Validate that the workbook source is either a valid URL or an existing local file path."""
        if not v:
            raise ValueError("Workbook source cannot be empty")

        # Check if it's a URL
        parsed = urlparse(v)
        if parsed.scheme in ("http", "https"):
            return v

        # Check if it's a local file path
        file_path = Path(v)
        if file_path.exists() and file_path.is_file():
            # Check if it's an Excel file
            if file_path.suffix.lower() not in [".xlsx", ".xls"]:
                raise ValueError("Local file must be an Excel file (.xlsx or .xls)")
            return str(file_path.resolve())

        raise ValueError(
            "Workbook source must be either a valid URL (http/https) or an existing local Excel file path"
        )

    @property
    def is_url(self) -> bool:
        """Check if the workbook source is a URL."""
        parsed = urlparse(self.workbook_source)
        return parsed.scheme in ("http", "https")

    @property
    def is_local_file(self) -> bool:
        """Check if the workbook source is a local file."""
        return not self.is_url


class AnalysisResponse(BaseModel):
    """Response model for the analysis endpoint."""

    analysis_file_url: str


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_workbook(request: AnalysisRequest):
    """
    Triggers the analysis of a workbook from a given URL or local file path.

    This endpoint initiates the analysis process, which includes:
    1. Loading the workbook from the provided URL or local file path
    2. Processing the data in a secure sandbox environment
    3. Generating an analysis report in a new Excel file
    4. In non-local environments, uploading the result to Google Cloud Storage

    All file operations are performed in a secure temporary directory to prevent
    unauthorized file system access.

    Args:
        request: The analysis request containing the workbook source (URL or local file path).

    Returns:
        A response containing the URL to the analysis file. In local environments,
        this will be a success message with the local file path. In non-local
        environments, this will be a public URL to the file in Google Cloud Storage.

    Raises:
        HTTPException: If an error occurs during the analysis process.
    """
    try:
        result_url = run_analysis(
            instruction=request.instruction,
            workbook_source=request.workbook_source,
            is_local_file=request.is_local_file,
        )
        return {"analysis_file_url": result_url}
    except Exception as e:
        logging.exception("Error during analysis")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )
