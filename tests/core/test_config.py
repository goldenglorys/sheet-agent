"""
Unit tests for the configuration module.

This test suite verifies the functionality of the SheetAgentSettings class and the
get_settings function, ensuring that configuration is loaded correctly from various
sources and that the system behaves as expected in different environments.
"""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.core.config import get_settings

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock import MockerFixture


def test_get_settings_is_cached() -> None:
    """
    Tests that get_settings returns a cached instance.
    """
    first_call = get_settings()
    second_call = get_settings()
    assert first_call is second_call


def test_settings_loading_from_env(monkeypatch: "MonkeyPatch") -> None:
    """
    Tests that settings are correctly loaded from environment variables.
    """
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key_from_env")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    settings = get_settings()

    assert settings.APP_ENVIRONMENT == "local"
    assert settings.OPENAI_API_KEY == "test_api_key_from_env"


def test_settings_loading_from_dotenv_file(
    monkeypatch: "MonkeyPatch", tmp_path: "MagicMock"
) -> None:
    """
    Tests that settings are correctly loaded from a .env file.
    """
    get_settings.cache_clear()
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text(
        'OPENAI_API_KEY="test_api_key_from_dotenv"\n'
        'OPENAI_API_BASE="https://api.openai.com/v1"\n'
    )

    settings = get_settings()

    assert settings.OPENAI_API_KEY == "test_api_key_from_dotenv"


def test_settings_missing_required_field() -> None:
    """
    Tests that a ValidationError is raised if a required field is missing.
    """
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        # Assuming OPENAI_API_KEY is not set in the test environment
        get_settings()


def test_gcp_secret_manager_loading(
    monkeypatch: "MonkeyPatch", mocker: "MockerFixture"
) -> None:
    """
    Tests that settings are correctly loaded from Google Secret Manager.
    """
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_PROJECT_ID", "test-project")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    mock_secret_manager_client = mocker.patch(
        "google.cloud.secretmanager.SecretManagerServiceClient"
    )
    mock_client_instance = mock_secret_manager_client.return_value

    def access_secret_version_side_effect(request: dict) -> MagicMock:
        secret_name = request["name"].split("/")[-2]
        payload = MagicMock()
        if secret_name == "OPENAI_API_KEY":
            payload.data = b"gcp_secret_key"
        else:
            # Simulate secret not found
            raise Exception("Secret not found")
        mock_response = MagicMock()
        mock_response.payload = payload
        return mock_response

    mock_client_instance.access_secret_version.side_effect = (
        access_secret_version_side_effect
    )

    settings = get_settings()

    assert settings.APP_ENVIRONMENT == "prod"
    assert settings.OPENAI_API_KEY == "gcp_secret_key"
    mock_client_instance.access_secret_version.assert_called()


def test_gcp_secret_manager_disabled_if_no_project_id(
    monkeypatch: "MonkeyPatch", mocker: "MockerFixture"
) -> None:
    """
    Tests that Google Secret Manager is not used if SECRET_PROJECT_ID is not set.
    """
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENVIRONMENT", "prod")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback_key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    monkeypatch.delenv("SECRET_PROJECT_ID", raising=False)

    mock_secret_manager_client = mocker.patch(
        "google.cloud.secretmanager.SecretManagerServiceClient"
    )
    mock_client_instance = mock_secret_manager_client.return_value

    settings = get_settings()

    assert settings.OPENAI_API_KEY == "fallback_key"
    mock_client_instance.access_secret_version.assert_not_called() 