"""Pytest configuration and fixtures.

Loads environment variables from .env file for local testing.
Provides fixtures for both unit and integration tests.
"""

import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

# Add src/functions to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "functions"))


def pytest_configure(config):
    """Load .env file and configure pytest markers before tests run."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests requiring Azure resources"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )

    try:
        from dotenv import load_dotenv

        # Load from project root .env file
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"\n[OK] Loaded environment from {env_path}")
        else:
            print(f"\n[WARN] No .env file found at {env_path}")
            print("  Copy .env.example to .env and fill in your values for integration tests")
    except ImportError:
        pass  # python-dotenv not installed, skip


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless RUN_INTEGRATION_TESTS is set."""
    if os.getenv("RUN_INTEGRATION_TESTS"):
        return  # Run all tests

    skip_integration = pytest.mark.skip(
        reason="Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture
def env_vars():
    """Fixture to check required environment variables.

    Use this fixture in integration tests that need real Azure resources.
    """
    required = [
        "DOC_INTEL_ENDPOINT",
        "DOC_INTEL_API_KEY",
        "COSMOS_ENDPOINT",
    ]

    missing = [var for var in required if not os.getenv(var)]

    if missing:
        pytest.skip(f"Missing required environment variables: {', '.join(missing)}")

    return {var: os.getenv(var) for var in required}


# ============================================================================
# Integration Test Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def integration_env():
    """Load integration test environment variables with defaults."""
    return {
        "doc_intel_endpoint": os.environ.get("DOC_INTEL_ENDPOINT", ""),
        "doc_intel_api_key": os.environ.get("DOC_INTEL_API_KEY", ""),
        "cosmos_endpoint": os.environ.get("COSMOS_ENDPOINT", ""),
        "cosmos_database": os.environ.get("COSMOS_DATABASE", "DocumentsDB"),
        "cosmos_container": os.environ.get("COSMOS_CONTAINER", "ProcessedDocuments"),
        "storage_connection_string": os.environ.get("STORAGE_CONNECTION_STRING", ""),
        "storage_container": os.environ.get("STORAGE_CONTAINER", "documents"),
        "test_blob_url": os.environ.get("TEST_BLOB_URL", ""),
    }


@pytest.fixture
def unique_test_id() -> str:
    """Generate a unique test ID for isolation."""
    return f"test_{uuid4().hex[:8]}"


@pytest.fixture
def test_source_file(unique_test_id: str) -> str:
    """Generate a unique source file path for test isolation."""
    return f"integration-test/{unique_test_id}.pdf"


@pytest.fixture
def test_document(unique_test_id: str, test_source_file: str) -> dict[str, Any]:
    """Create a test document with required fields."""
    from datetime import datetime, timezone

    return {
        "id": unique_test_id,
        "sourceFile": test_source_file,
        "processedAt": datetime.now(timezone.utc).isoformat(),
        "modelId": "test-model",
        "status": "completed",
        "fields": {"testField": "testValue", "amount": 100.50},
        "confidence": {"testField": 0.98, "amount": 0.95},
    }


@pytest.fixture
def test_tenant_document(unique_test_id: str, test_source_file: str) -> dict[str, Any]:
    """Create a test document with tenant isolation fields."""
    from datetime import datetime, timezone

    return {
        "id": unique_test_id,
        "sourceFile": test_source_file,
        "tenantId": f"tenant_{unique_test_id[:4]}",
        "processedAt": datetime.now(timezone.utc).isoformat(),
        "modelId": "test-model",
        "status": "completed",
        "fields": {"vendorName": "Test Corp"},
        "confidence": {"vendorName": 0.99},
    }
