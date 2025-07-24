import logging
from typing import Dict, Any
from datetime import datetime
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl, Field, field_validator

from app.services.analysis_service import run_analysis
from app.utils.validation import validate_analysis_request, ValidationError
from app.utils.exceptions import (
    SheetAgentError,
    AIModelError,
    SandboxError,
    WorkbookError,
)

logger = logging.getLogger(__name__)

router = APIRouter()
PROMPT = f"""You are an expert financial analyst agent. Your goal is to analyze an open posts list from a company, which contains unpaid invoices and credits.

## Overall Goal
Complete a multi-step financial analysis of the provided spreadsheet and write the results into a new sheet named "Analysis" following the EXACT format specified below.

## Analysis Plan

### 1. Identify Row Types
Start by using the `get_row_types` tool. You will need to identify the sheet name and the column letter that contains the invoice amounts to use this tool. The tool will return the row numbers for "invoices" (positive amounts), "credits" (negative amounts), and "cumulative" rows (summary/total rows).

### 2. Use the Row Lists
Once you have the lists of row numbers, use them for all subsequent calculations. Do not re-calculate these lists.

### 3. Perform Calculations & Write to Analysis Sheet
Use the `python_executor` tool to create the "Analysis" sheet with the following EXACT structure:

## REQUIRED OUTPUT FORMAT IN ANALYSIS SHEET

### Row 1 Headers:
```
A1: "Sum of Invoice Amounts"
B1: "Sum of Credit Amounts" 
C1: "Maturity Cluster"
D1: "Total Amount"
E1: "Percentage"
F1: "Credit Maturity Cluster"
G1: "Total Amount"
H1: "Percentage"
I1: "Cumulative Row Numbers"
J1: "Invoice Row Numbers"
K1: "Credit Row Numbers"
L1: "Incomplete Invoice Rows"
M1: "Incomplete Credit Rows"
```

### Data Structure:
- **Column A**: Single value - total of all invoice amounts
- **Column B**: Single value - total of all credit amounts  
- **Columns C-E**: Invoice aging buckets:
  - Row 2: "Not mature" | amount | percentage
  - Row 3: "1-30 days" | amount | percentage  
  - Row 4: "31-60 days" | amount | percentage
  - Row 5: ">60 days" | amount | percentage
- **Columns F-H**: Credit aging buckets (same structure)
- **Columns I-K**: Row number lists (one number per row)
- **Columns L-M**: Incomplete row numbers (missing required data)

## Detailed Requirements

### 4. Calculate Totals
- Sum all invoice amounts (positive values from invoice rows)
- Sum all credit amounts (negative values from credit rows)

### 5. Create Aging Reports
- **Invoice Aging**: Group invoice rows by maturity: Not mature, 1-30 days, 31-60 days, >60 days
- **Credit Aging**: Same grouping for credit rows
- **Maturity calculation**: `(today's date - due date).days`
- **Percentages**: Each bucket's percentage of total invoices/credits

### 6. Row Classification Lists
- List all cumulative row numbers (summary/total rows)
- List all invoice row numbers (positive amounts, non-cumulative)
- List all credit row numbers (negative amounts, non-cumulative)

### 7. Data Completeness Check
- Identify invoice rows missing: invoice numbers, amounts, or due dates
- Identify credit rows missing: invoice numbers, amounts, or due dates

## Important Rules
- Today's date is: **{datetime.now().strftime("%dth of %B %Y")}**
- The `workbook` is already loaded in the sandbox
- Use EXACT column positioning as specified above
- Write one value per cell, lists go vertically down columns
- Calculate percentages to 2 decimal places

Take a deep breath and execute step-by-step. Start with `get_row_types`.
"""

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
    session_id: str
    success: bool = True
    performance_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Comprehensive analysis performance metrics"
    )


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
        # Validate request before processing
        validate_analysis_request(
            workbook_source=request.workbook_source,
            is_local_file=request.is_local_file,
            instruction=request.instruction,
        )

        # Run analysis
        result = run_analysis(
            instruction=request.instruction,
            workbook_source=request.workbook_source,
            is_local_file=request.is_local_file,
        )
        return AnalysisResponse(
            analysis_file_url=result["analysis_file_url"],
            session_id=result["session_id"],
            performance_metrics=result["performance_metrics"],
            success=result["success"],
        )
    except ValidationError as e:
        logger.warning(f"Validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")

    except WorkbookError as e:
        logger.error(f"Workbook error: {str(e)}")
        raise HTTPException(
            status_code=422, detail=f"Workbook processing failed: {str(e)}"
        )

    except AIModelError as e:
        logger.error(f"AI model error: {str(e)}")
        raise HTTPException(
            status_code=503, detail="AI service temporarily unavailable"
        )

    except SandboxError as e:
        logger.error(f"Sandbox error: {str(e)}")
        raise HTTPException(status_code=500, detail="Analysis environment error")

    except SheetAgentError as e:
        logger.error(
            f"SheetAgent error: {str(e)} | Context: {getattr(e, 'context', {})}"
        )
        raise HTTPException(status_code=500, detail="Analysis failed")

    except Exception as e:
        logger.exception("Unexpected error during analysis")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
