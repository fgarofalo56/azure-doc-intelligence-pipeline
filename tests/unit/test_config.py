"""Unit tests for the configuration module."""

import os
from unittest.mock import patch

import pytest


class TestConfigurationError:
    """Tests for ConfigurationError exception."""

    def test_error_with_single_missing_var(self):
        """Test error message with one missing variable."""
        from src.functions.config import ConfigurationError

        error = ConfigurationError(["DOC_INTEL_ENDPOINT"])

        assert error.missing_vars == ["DOC_INTEL_ENDPOINT"]
        assert "DOC_INTEL_ENDPOINT" in str(error)

    def test_error_with_multiple_missing_vars(self):
        """Test error message with multiple missing variables."""
        from src.functions.config import ConfigurationError

        error = ConfigurationError(["VAR1", "VAR2", "VAR3"])

        assert error.missing_vars == ["VAR1", "VAR2", "VAR3"]
        assert "VAR1" in str(error)
        assert "VAR2" in str(error)
        assert "VAR3" in str(error)


class TestConfig:
    """Tests for Config class."""

    @pytest.fixture
    def valid_env_vars(self):
        """Return a valid set of environment variables."""
        return {
            "DOC_INTEL_ENDPOINT": "https://doc-intel.cognitiveservices.azure.com",
            "DOC_INTEL_API_KEY": "test-api-key",
            "COSMOS_ENDPOINT": "https://cosmos.documents.azure.com",
            "COSMOS_DATABASE": "TestDB",
            "COSMOS_CONTAINER": "TestContainer",
        }

    def test_from_environment_success(self, valid_env_vars):
        """Test successful configuration loading."""
        from src.functions.config import Config

        with patch.dict(os.environ, valid_env_vars, clear=True):
            config = Config.from_environment()

        assert config.doc_intel_endpoint == "https://doc-intel.cognitiveservices.azure.com"
        assert config.doc_intel_api_key == "test-api-key"
        assert config.cosmos_endpoint == "https://cosmos.documents.azure.com"
        assert config.cosmos_database == "TestDB"
        assert config.cosmos_container == "TestContainer"

    def test_from_environment_missing_required_vars(self):
        """Test error when required variables are missing."""
        from src.functions.config import Config, ConfigurationError

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                Config.from_environment()

        assert "DOC_INTEL_ENDPOINT" in str(exc_info.value)
        assert "COSMOS_ENDPOINT" in str(exc_info.value)

    def test_from_environment_with_defaults(self, valid_env_vars):
        """Test that defaults are applied for optional variables."""
        from src.functions.config import Config

        with patch.dict(os.environ, valid_env_vars, clear=True):
            config = Config.from_environment()

        assert config.function_timeout == 230
        assert config.log_level == "INFO"
        assert config.max_concurrent_requests == 10
        assert config.default_model_id == "prebuilt-layout"
        assert config.sas_token_expiry_hours == 1
        assert config.dead_letter_container == "_dead_letter"
        assert config.max_retry_attempts == 3

    def test_from_environment_with_custom_values(self, valid_env_vars):
        """Test that custom values override defaults."""
        from src.functions.config import Config

        custom_env = {
            **valid_env_vars,
            "FUNCTION_TIMEOUT": "300",
            "LOG_LEVEL": "DEBUG",
            "MAX_CONCURRENT_REQUESTS": "5",
            "DEFAULT_MODEL_ID": "custom-model",
        }

        with patch.dict(os.environ, custom_env, clear=True):
            config = Config.from_environment()

        assert config.function_timeout == 300
        assert config.log_level == "DEBUG"
        assert config.max_concurrent_requests == 5
        assert config.default_model_id == "custom-model"

    def test_from_environment_storage_connection_string_priority(self, valid_env_vars):
        """Test storage connection string tries multiple env vars."""
        from src.functions.config import Config

        # Test STORAGE_CONNECTION_STRING is used first
        env_with_storage = {
            **valid_env_vars,
            "STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;Storage1",
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;WebJobs",
        }

        with patch.dict(os.environ, env_with_storage, clear=True):
            config = Config.from_environment()
            assert "Storage1" in config.storage_connection_string

    def test_from_environment_azure_web_jobs_storage(self, valid_env_vars):
        """Test AzureWebJobsStorage is used as fallback."""
        from src.functions.config import Config

        env_with_webjobs = {
            **valid_env_vars,
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;WebJobs",
        }

        with patch.dict(os.environ, env_with_webjobs, clear=True):
            config = Config.from_environment()
            assert "WebJobs" in config.storage_connection_string

    def test_from_environment_azure_storage_connection_string(self, valid_env_vars):
        """Test AZURE_STORAGE_CONNECTION_STRING is used as last fallback."""
        from src.functions.config import Config

        env_with_azure = {
            **valid_env_vars,
            "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;Azure",
        }

        with patch.dict(os.environ, env_with_azure, clear=True):
            config = Config.from_environment()
            assert "Azure" in config.storage_connection_string

    def test_from_environment_no_storage_connection(self, valid_env_vars):
        """Test storage connection string is None when not configured."""
        from src.functions.config import Config

        with patch.dict(os.environ, valid_env_vars, clear=True):
            config = Config.from_environment()
            assert config.storage_connection_string is None

    def test_from_environment_webhook_url(self, valid_env_vars):
        """Test webhook URL is loaded."""
        from src.functions.config import Config

        env_with_webhook = {
            **valid_env_vars,
            "WEBHOOK_URL": "https://webhook.example.com/notify",
        }

        with patch.dict(os.environ, env_with_webhook, clear=True):
            config = Config.from_environment()
            assert config.webhook_url == "https://webhook.example.com/notify"


class TestGetConfig:
    """Tests for get_config singleton function."""

    def test_get_config_creates_singleton(self):
        """Test get_config returns singleton instance."""
        import src.functions.config as config_module
        from src.functions.config import get_config

        # Reset singleton
        config_module._config = None

        valid_env = {
            "DOC_INTEL_ENDPOINT": "https://test.cognitiveservices.azure.com",
            "DOC_INTEL_API_KEY": "key",
            "COSMOS_ENDPOINT": "https://test.documents.azure.com",
            "COSMOS_DATABASE": "DB",
            "COSMOS_CONTAINER": "Container",
        }

        with patch.dict(os.environ, valid_env, clear=True):
            config1 = get_config()
            config2 = get_config()

        assert config1 is config2
