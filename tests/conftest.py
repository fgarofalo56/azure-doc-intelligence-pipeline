"""Pytest configuration and fixtures.

Loads environment variables from .env file for local testing.
Provides fixtures for both unit and integration tests.

Emulator Support:
    This module supports running integration tests against Azure emulators:
    - Azurite for Azure Blob Storage
    - Cosmos DB Linux Emulator

    To run emulator-based tests:
    1. Start emulators: docker compose --profile emulators up -d
    2. Run tests: RUN_EMULATOR_TESTS=1 uv run pytest tests/integration/ -m emulator
"""

import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

# Add src/functions to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "functions"))

# =============================================================================
# EMULATOR CONNECTION CONSTANTS
# =============================================================================

# Azurite default connection string (well-known development account)
AZURITE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    "QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;"
    "TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
)

# Cosmos DB Emulator default settings
COSMOS_EMULATOR_ENDPOINT = "https://localhost:8081"
COSMOS_EMULATOR_KEY = (
    "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
)


def pytest_configure(config):
    """Load .env file and configure pytest markers before tests run."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests requiring Azure resources"
    )
    config.addinivalue_line(
        "markers", "emulator: marks tests that run against local emulators (Azurite, Cosmos DB)"
    )
    config.addinivalue_line("markers", "slow: marks tests as slow running")

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
    """Skip integration/emulator tests unless explicitly enabled."""
    run_integration = os.getenv("RUN_INTEGRATION_TESTS")
    run_emulator = os.getenv("RUN_EMULATOR_TESTS")

    skip_integration = pytest.mark.skip(
        reason="Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    skip_emulator = pytest.mark.skip(
        reason="Emulator tests disabled. Start emulators and set RUN_EMULATOR_TESTS=1 to enable."
    )

    for item in items:
        # Handle emulator tests
        if "emulator" in item.keywords:
            if not run_emulator:
                item.add_marker(skip_emulator)
        # Handle integration tests (but not emulator tests which have their own flag)
        elif "integration" in item.keywords:
            if not run_integration:
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


# ============================================================================
# Emulator Test Fixtures
# ============================================================================


def is_emulator_available(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if an emulator is available at the given host:port."""
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


@pytest.fixture(scope="session")
def azurite_available() -> bool:
    """Check if Azurite emulator is running."""
    return is_emulator_available("127.0.0.1", 10000)


@pytest.fixture(scope="session")
def cosmos_emulator_available() -> bool:
    """Check if Cosmos DB emulator is running."""
    return is_emulator_available("127.0.0.1", 8081)


@pytest.fixture(scope="module")
def azurite_blob_service(azurite_available):
    """Create BlobService connected to Azurite emulator.

    Usage:
        @pytest.mark.emulator
        def test_blob_upload(azurite_blob_service):
            blob_service = azurite_blob_service
            # ... test with blob_service
    """
    if not azurite_available:
        pytest.skip("Azurite emulator not available. Start with: docker compose up azurite -d")

    from services.blob_service import BlobService

    return BlobService(connection_string=AZURITE_CONNECTION_STRING)


@pytest.fixture(scope="module")
def azurite_test_container(azurite_blob_service):
    """Create a test container in Azurite and clean up after tests.

    Returns the container name for use in tests.
    """
    from azure.storage.blob import BlobServiceClient

    container_name = f"emulator-test-{uuid4().hex[:8]}"

    # Create container using the SDK directly
    blob_service_client = BlobServiceClient.from_connection_string(AZURITE_CONNECTION_STRING)
    container_client = blob_service_client.create_container(container_name)

    yield container_name

    # Cleanup: delete all blobs and the container
    try:
        for blob in container_client.list_blobs():
            container_client.delete_blob(blob.name)
        container_client.delete_container()
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture(scope="module")
def cosmos_emulator_service(cosmos_emulator_available):
    """Create CosmosService connected to Cosmos DB emulator.

    Note: The Cosmos DB emulator uses a self-signed certificate.
    This fixture configures the service to work with the emulator.

    Usage:
        @pytest.mark.emulator
        async def test_cosmos_save(cosmos_emulator_service):
            cosmos_service = cosmos_emulator_service
            # ... test with cosmos_service
    """
    if not cosmos_emulator_available:
        pytest.skip(
            "Cosmos DB emulator not available. Start with: docker compose up cosmos-emulator -d"
        )

    # Import here to avoid import errors if azure-cosmos not installed
    from azure.cosmos import CosmosClient

    from services.cosmos_service import CosmosService

    # Create a custom client that trusts the emulator's self-signed certificate
    # The emulator key is well-known and safe to use
    client = CosmosClient(
        url=COSMOS_EMULATOR_ENDPOINT,
        credential=COSMOS_EMULATOR_KEY,
        connection_verify=False,  # Disable SSL verification for emulator
    )

    # Create database and container if they don't exist
    database_name = "EmulatorTestDB"
    container_name = "TestDocuments"

    database = client.create_database_if_not_exists(database_name)
    database.create_container_if_not_exists(
        id=container_name,
        partition_key={"paths": ["/sourceFile"], "kind": "Hash"},
    )

    return CosmosService(
        endpoint=COSMOS_EMULATOR_ENDPOINT,
        database_name=database_name,
        container_name=container_name,
        credential=COSMOS_EMULATOR_KEY,  # Use key auth for emulator
    )


@pytest.fixture
def emulator_test_id() -> str:
    """Generate a unique test ID for emulator test isolation."""
    return f"emulator_test_{uuid4().hex[:8]}"


@pytest.fixture
def emulator_source_file(emulator_test_id: str) -> str:
    """Generate a unique source file path for emulator test isolation."""
    return f"emulator-test/{emulator_test_id}.pdf"
