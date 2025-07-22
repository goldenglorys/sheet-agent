"""
Google Cloud Storage utility module for SheetAgent.

This module provides functions for interacting with Google Cloud Storage,
including uploading files and generating public URLs. It encapsulates all
GCS-specific functionality to provide a clean interface for the rest of the application.

Setup Requirements:
1. Set GCS_BUCKET_NAME in your .env file
2. For Docker deployment:
   - Place your GCP service account JSON key file as 'credentials.json' in the project root
   - The docker-compose.yml will mount this file and set GOOGLE_APPLICATION_CREDENTIALS
3. For local development without Docker:
   - Set GOOGLE_APPLICATION_CREDENTIALS environment variable to point to your credentials file
   - Or use: export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/credentials.json"
"""

from pathlib import Path
from google.cloud import storage
from google.api_core import exceptions
import logging

def upload_to_gcs(file_path: Path, bucket_name: str, destination_blob_name: str) -> str:
    """
    Uploads a file to a GCS bucket and returns its public URL.
    
    This function handles the upload process to Google Cloud Storage,
    including error handling and logging. The file is made publicly
    accessible, and its URL is returned for easy access.

    Args:
        file_path: The local path to the file to upload.
        bucket_name: The name of the GCS bucket.
        destination_blob_name: The name of the blob in the bucket.

    Returns:
        The public URL of the uploaded file.
        
    Raises:
        FileNotFoundError: If the local file does not exist.
        google.cloud.exceptions.NotFound: If the bucket does not exist.
        google.cloud.exceptions.GoogleAPICallError: On other API errors.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found at {file_path}")

    storage_client = storage.Client()
    
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(str(file_path))

        logging.info(f"File {file_path} uploaded to {destination_blob_name}.")
        
        return blob.public_url
    except exceptions.NotFound:
        logging.error(f"Bucket {bucket_name} not found.")
        raise
    except exceptions.GoogleAPICallError as e:
        logging.error(f"Failed to upload to GCS: {e}")
        raise 