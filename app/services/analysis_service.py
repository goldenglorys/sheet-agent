import logging
import shutil
import tempfile
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.core.sandbox import Sandbox
from app.core.metrics import AnalysisMetrics
from app.dataset.dataloader import load_problem
from app.graph.graph import SheetAgentGraph
from app.utils.enumeration import MODEL_TYPE
from app.utils.gcs import upload_to_gcs

# Configure logger
logger = logging.getLogger(__name__)


def run_analysis(
    instruction: str, workbook_source: str, is_local_file: bool = False
) -> Dict[str, Any]:
    """
    Runs the open post analysis on the given workbook.

    All file operations are executed within a secure temporary directory to prevent
    unauthorized file system access. The analysis process loads the workbook from
    either a URL or local file path, processes it, and generates an analysis file.

    In local environment, returns a success message with the local file path.
    In development and production environments, uploads the output file to
    Google Cloud Storage and returns the public URL.

    Args:
        instruction: The instruction for the analysis.
        workbook_source: The URL or local file path to the workbook file.
        is_local_file: Whether the workbook_source is a local file path.

    Returns:
        In local environment: A success message with the local file path.
        In non-local environments: The public URL of the uploaded analysis file in Google Cloud Storage.

    Raises:
        ValueError: If GCS_BUCKET_NAME environment variable is not set in non-local environments.
        Exception: For any errors during file processing or GCS upload.
    """
    source_type = "local file" if is_local_file else "URL"
    logger.info(
        f"Starting analysis for workbook from {source_type}: {workbook_source} with instruction: {instruction}"
    )

    try:
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str).resolve()

            # Generate unique session ID for this analysis run
            session_id = (
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            )

            # Create session-specific directories
            session_output_dir = temp_dir / "output" / session_id
            db_path = temp_dir / "db_path"

            session_output_dir.mkdir(parents=True, exist_ok=True)
            db_path.mkdir(exist_ok=True)
            logger.info(f"Created session output directory: {session_output_dir}")

            logger.info(f"Created session directory: {session_id}")

            # Generate unique workbook filename
            unique_id = uuid.uuid4()
            local_workbook_path = session_output_dir / f"{unique_id}_workbook.xlsx"

            # Create sandbox and load problem
            logger.info("Creating sandbox instance")
            sandbox = Sandbox(base_dir=temp_dir)
            logger.info("Loading problem from workbook")
            problem = load_problem(
                workbook_path=local_workbook_path,
                db_path=db_path,
                instruction=instruction,
                workbook_source=workbook_source,
                is_local_file=is_local_file,
            )

            # Create agent graph with session output directory
            logger.info("Creating SheetAgentGraph")
            agent_graph = SheetAgentGraph(
                problem=problem,
                output_dir=session_output_dir,
                sandbox=sandbox,
            )
            
            # Create metrics tracker and use context manager
            metrics_tracker = AnalysisMetrics()

            metrics_tracker.start_phase("preprocessing")
            # Pass metrics tracker to agent graph
            agent_graph.metrics_tracker = metrics_tracker
            metrics_tracker.end_phase("preprocessing")

            # Use context manager for automatic timing and memory tracking
            with metrics_tracker:
                logger.info("Running SheetAgentGraph")
                agent_graph.run()
                logger.info("SheetAgentGraph execution completed")
                
                # Record output file size with file operations timing
                metrics_tracker.start_phase("file_operations")
                output_file_path = session_output_dir / "workbook_new.xlsx"
                if output_file_path.exists():
                    metrics_tracker.record_file_size(output_file_path, "output")
                metrics_tracker.end_phase("file_operations")

            final_metrics = metrics_tracker.get_metrics()
        
            # Handle output based on environment
            settings = get_settings()
            if settings.APP_ENVIRONMENT == "local":
                # Create persistent session-based directory structure
                persistent_base_dir = (
                    Path("/app/sandbox/output")
                    if Path("/app/sandbox").exists()
                    else Path("./output")
                )
                persistent_session_dir = persistent_base_dir / session_id
                persistent_session_dir.mkdir(parents=True, exist_ok=True)

                # Copy all session files to persistent storage
                for file_path in session_output_dir.glob("*"):
                    if file_path.is_file():
                        shutil.copy2(file_path, persistent_session_dir / file_path.name)

                logger.info(
                    f"Analysis session {session_id} saved to: {persistent_session_dir}"
                )
                result_url = f"Successfully generated analysis session {session_id} to: {persistent_session_dir}"
            else:
                # Non-local environment: upload to GCS
                bucket_name = settings.GCS_BUCKET_NAME
                if not bucket_name:
                    logger.error("GCS_BUCKET_NAME environment variable is not set")
                    raise ValueError(
                        "GCS_BUCKET_NAME environment variable is not set but required in non-local environment"
                    )

                # Generate a unique name for the file in GCS
                output_file_path = session_output_dir / "workbook_new.xlsx"
                destination_blob_name = f"analysis/{unique_id}_analysis.xlsx"

                # Upload the file to GCS and get the public URL
                logger.info(f"Uploading output file to GCS bucket: {bucket_name}")
                result_url = upload_to_gcs(output_file_path, bucket_name, destination_blob_name)
                logger.info(f"File uploaded successfully to GCS: {result_url}")

            # Return result with metrics
            return {
                "analysis_file_url": result_url,
                "session_id": session_id,
                "performance_metrics": final_metrics,
                "success": True
            }
    except Exception as e:
        logger.exception(f"Error during analysis: {str(e)}")
        raise
