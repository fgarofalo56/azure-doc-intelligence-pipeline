# Testing Guide

This directory contains tests for the Azure Document Intelligence PDF Processing Pipeline.

## Test Categories

### Unit Tests (`tests/unit/`)

Fast, isolated tests that mock external dependencies. Run without any Azure resources.

```bash
# Run all unit tests
uv run pytest tests/unit/ -v

# Run with coverage
uv run pytest tests/unit/ --cov=src --cov-report=html
```

### Integration Tests (`tests/integration/`)

Tests that interact with real Azure services. Require proper credentials.

```bash
# Set required environment variables (or use .env file)
export STORAGE_CONNECTION_STRING="..."
export COSMOS_ENDPOINT="..."
export DOC_INTEL_ENDPOINT="..."
export DOC_INTEL_API_KEY="..."

# Run integration tests
RUN_INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v -m integration
```

### Emulator Tests (`tests/integration/test_*_emulator.py`)

Tests that run against local Azure emulators (Azurite, Cosmos DB Emulator).
CI-friendly - no real Azure resources required.

```bash
# Start emulators
docker compose --profile emulators up -d

# Wait for Cosmos DB emulator to be healthy (takes ~60 seconds)
docker compose logs -f cosmos-emulator

# Run emulator tests
RUN_EMULATOR_TESTS=1 uv run pytest tests/integration/ -v -m emulator

# Stop emulators when done
docker compose --profile emulators down
```

## Emulator Setup

### Azurite (Storage Emulator)

Azurite emulates Azure Blob, Queue, and Table Storage services.

```bash
# Start Azurite only
docker compose up azurite -d

# Connection string (well-known dev credentials)
DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;
```

### Cosmos DB Emulator

The Linux Cosmos DB Emulator provides a local Cosmos DB environment.

```bash
# Start Cosmos DB emulator
docker compose up cosmos-emulator -d

# Wait for startup (check logs)
docker compose logs -f cosmos-emulator

# Emulator endpoint
https://localhost:8081

# Well-known emulator key
C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==
```

**Note:** The Cosmos DB emulator uses a self-signed certificate. The test fixtures automatically disable SSL verification for emulator connections.

## Test Fixtures

Common fixtures are defined in `conftest.py`:

### Unit Test Fixtures
- `unique_test_id`: Unique ID for test isolation
- `test_source_file`: Unique source file path
- `test_document`: Sample document with all required fields
- `test_tenant_document`: Sample document with tenant isolation

### Integration Test Fixtures
- `integration_env`: Environment variables for real Azure services
- `env_vars`: Validation fixture that skips tests if credentials missing

### Emulator Fixtures
- `azurite_available`: Checks if Azurite is running
- `cosmos_emulator_available`: Checks if Cosmos DB emulator is running
- `azurite_blob_service`: BlobService connected to Azurite
- `azurite_test_container`: Creates/cleans up test container
- `cosmos_emulator_service`: CosmosService connected to emulator
- `emulator_test_id`: Unique ID for emulator test isolation
- `emulator_source_file`: Unique source file for emulator tests

## Test Markers

```python
@pytest.mark.integration  # Requires real Azure resources
@pytest.mark.emulator     # Runs against local emulators
@pytest.mark.slow         # Slow-running tests
```

## CI/CD Integration

### GitHub Actions Example

```yaml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: uv run pytest tests/unit/ --cov=src

  emulator-tests:
    runs-on: ubuntu-latest
    services:
      azurite:
        image: mcr.microsoft.com/azure-storage/azurite
        ports:
          - 10000:10000
          - 10001:10001
          - 10002:10002
    steps:
      - uses: actions/checkout@v4
      - name: Run emulator tests
        env:
          RUN_EMULATOR_TESTS: "1"
        run: uv run pytest tests/integration/ -m emulator
```

## Writing Tests

### Unit Test Example

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

class TestMyService:
    @pytest.mark.asyncio
    async def test_process_document(self):
        # Arrange
        mock_client = MagicMock()
        service = MyService(client=mock_client)

        # Act
        result = await service.process("test.pdf")

        # Assert
        assert result["status"] == "completed"
```

### Emulator Test Example

```python
import pytest

pytestmark = pytest.mark.emulator

class TestBlobOperations:
    def test_upload_blob(self, azurite_blob_service, azurite_test_container):
        """Test uploading a blob via Azurite emulator."""
        blob_url = azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name="test.txt",
            content=b"test content",
        )
        assert blob_url is not None
```

## Troubleshooting

### Cosmos DB Emulator Issues

1. **Emulator won't start**: Check Docker resources (needs ~2GB RAM)
2. **SSL errors**: The test fixtures disable SSL verification automatically
3. **Connection refused**: Wait for emulator to fully start (~60 seconds)

### Azurite Issues

1. **Port conflicts**: Check if ports 10000-10002 are available
2. **Permission denied**: Ensure Docker has access to the data volume

### Test Discovery Issues

1. **Tests not found**: Ensure files are named `test_*.py`
2. **Fixtures not available**: Check imports in `conftest.py`
