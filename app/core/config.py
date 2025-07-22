"""
Core configuration module for the SheetAgent application.

This module provides a centralized and type-safe way to manage application settings
using Pydantic's BaseSettings. It supports loading settings from environment
variables and .env files, with environment-specific logic for local,
development, and production environments.
"""

import functools
import logging
from typing import Any, Dict, Literal, Tuple, Type
import os

from google.cloud import secretmanager
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

logger = logging.getLogger(__name__)


# Helper base class to avoid recursion when fetching GCP-controlling env vars.
class _AppEnvSettings(BaseSettings):
    """Defines settings needed to control GCP secret loading."""

    APP_ENVIRONMENT: Literal["local", "dev", "prod"] = "local"
    SECRET_PROJECT_ID: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class GoogleSecretManagerSource(PydanticBaseSettingsSource):
    """
    A Pydantic settings source that loads secrets from Google Secret Manager.
    """

    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        # Get settings required for GCP, without triggering full settings instantiation
        gcp_env = _AppEnvSettings()
        self.project_id = gcp_env.SECRET_PROJECT_ID
        self.app_env = gcp_env.APP_ENVIRONMENT

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        # This method is called for every field in the settings class.
        # We don't need to implement it for this source as we fetch all secrets in __call__.
        return None, field_name, False

    def __call__(self) -> Dict[str, Any]:
        """
        Load secrets from Google Secret Manager if in a non-local environment.
        """
        secrets: Dict[str, Any] = {}

        if self.app_env in ("dev", "prod"):
            if not self.project_id:
                logger.warning(
                    "APP_ENVIRONMENT is '%s' but SECRET_PROJECT_ID is not set. "
                    "Skipping Google Secret Manager.",
                    self.app_env,
                )
                return secrets

            try:
                client = secretmanager.SecretManagerServiceClient()
                for field_name in self.settings_cls.model_fields:
                    # Don't try to fetch fields that are already part of the env settings
                    if field_name in _AppEnvSettings.model_fields:
                        continue

                    secret_name = f"projects/{self.project_id}/secrets/{field_name}/versions/latest"
                    try:
                        response = client.access_secret_version(
                            request={"name": secret_name}
                        )
                        secrets[field_name] = response.payload.data.decode(
                            "UTF-8"
                        )
                        logger.info(
                            f"Successfully loaded secret '{field_name}' from GCP."
                        )
                    except Exception:
                        logger.info(
                            f"Secret '{field_name}' not found in Google Secret Manager."
                        )
            except Exception as e:
                logger.error(f"Failed to connect to Google Secret Manager: {e}")

        return secrets


class SheetAgentSettings(BaseSettings):
    """
    Defines the application's settings, loaded from environment variables.

    Attributes:
        APP_ENVIRONMENT: The application environment ('local', 'dev', or 'prod').
        ENVIRONMENT: The runtime environment.
        HOST: The host on which the application runs.
        PORT: The port on which the application listens.
        OPENAI_API_BASE: The base URL for the OpenAI API.
        OPENAI_API_KEY: The API key for OpenAI services.
        SECRET_PROJECT_ID: The Google Cloud project ID for Secret Manager.
        GCS_BUCKET_NAME: The name of the Google Cloud Storage bucket.
        GOOGLE_APPLICATION_CREDENTIALS: The path to the Google Cloud credentials file.
        LANGCHAIN_TRACING_V2: Whether to enable LangSmith tracing.
        LANGCHAIN_ENDPOINT: The endpoint URL for LangSmith.
        LANGCHAIN_API_KEY: The API key for LangSmith.
        LANGCHAIN_PROJECT: The project name for LangSmith tracing.
    """

    APP_ENVIRONMENT: Literal["local", "dev", "prod"] = "local"
    ENVIRONMENT: str = "local"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # OpenAI API Configuration
    OPENAI_API_BASE: str
    OPENAI_API_KEY: str
    # Google Cloud Settings
    SECRET_PROJECT_ID: str | None = None
    GCS_BUCKET_NAME: str | None = None
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None
    
    # LangSmith Configuration
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str 
    LANGSMITH_API_KEY: str
    LANGSMITH_PROJECT: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """
        Customize the settings sources to include Google Secret Manager.
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            GoogleSecretManagerSource(settings_cls),
            file_secret_settings,
        )


@functools.lru_cache
def get_settings() -> SheetAgentSettings:
    """
    Returns a cached singleton instance of the SheetAgentSettings.

    This function ensures that the settings are loaded only once and provides
    a consistent, shared configuration object across the application.

    Returns:
        An instance of SheetAgentSettings.
    """
    settings = SheetAgentSettings()
    
    # Explicitly set OS environment variables for LangSmith
    if settings.LANGSMITH_TRACING:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    
    return settings