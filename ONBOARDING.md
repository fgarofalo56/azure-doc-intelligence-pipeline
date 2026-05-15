# Developer Onboarding Guide

Welcome to the Azure Document Intelligence PDF Processing Pipeline! This guide will get you up and running with local development.

## Prerequisites

Before starting, ensure you have:

- **Python 3.10+** installed
- **UV** package manager ([installation](https://github.com/astral-sh/uv))
- **Azure Functions Core Tools v4** ([installation](https://docs.microsoft.com/azure/azure-functions/functions-run-local))
- **Azure CLI** ([installation](https://docs.microsoft.com/cli/azure/install-azure-cli))
- **Git** for version control
- An **Azure subscription** (for deployed resources)

## Quick Start (5 minutes)

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd FormExtraction

# Create virtual environment and install dependencies
uv venv
uv sync
```

### 2. Configure Local Settings

Copy the template and add your Azure resource details:

```bash
cp src/functions/local.settings.template.json src/functions/local.settings.json
```

Edit `src/functions/local.settings.json`:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "<your-storage-connection-string>",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "DOC_INTEL_ENDPOINT": "https://<your-instance>.cognitiveservices.azure.com/",
    "DOC_INTEL_API_KEY": "<your-api-key>",
    "COSMOS_ENDPOINT": "https://<your-instance>.documents.azure.com:443/",
    "COSMOS_DATABASE": "DocumentsDB",
    "COSMOS_CONTAINER": "ExtractedDocuments"
  }
}
```

### 3. Run Locally

```bash
cd src/functions
func start
```

The function app will start at `http://localhost:7071`. Test with:

```bash
curl http://localhost:7071/api/v1/health
```

## Project Structure

```
FormExtraction/
├── src/functions/           # Azure Functions application
│   ├── function_app.py      # HTTP triggers and main logic
│   ├── config.py            # Configuration management
│   └── services/            # Business logic services
│       ├── document_service.py    # Document Intelligence integration
│       ├── cosmos_service.py      # Cosmos DB operations
│       ├── blob_service.py        # Blob storage operations
│       ├── pdf_service.py         # PDF splitting
│       ├── circuit_breaker.py     # Resilience patterns
│       ├── dead_letter_queue.py   # Failed message handling
│       └── audit_service.py       # Audit logging
├── tests/
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── infra/                   # Bicep infrastructure
│   ├── main.bicep           # Main deployment template
│   └── modules/             # Reusable modules
└── docs/                    # Documentation
```

## Development Workflow

### Running Tests

```bash
# All unit tests
uv run pytest tests/unit/ -v

# With coverage report
uv run pytest tests/unit/ --cov=src --cov-report=html

# Specific test file
uv run pytest tests/unit/test_document_service.py -v

# Integration tests (requires deployed resources)
uv run pytest tests/integration/ -v --run-integration
```

### Code Quality

```bash
# Lint code
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/

# Type checking (optional)
uv run mypy src/functions/
```

### Making Changes

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and add tests
3. Run tests and linting: `uv run pytest && uv run ruff check`
4. Commit with meaningful messages
5. Create a pull request

## Key Concepts

### Document Processing Flow

1. **Submit**: Client sends PDF URL to `/api/v1/process`
2. **Split**: Multi-page PDFs are split into 2-page form chunks
3. **Extract**: Each chunk processed by Document Intelligence
4. **Store**: Results saved to Cosmos DB with PDF links
5. **Notify**: Optional webhook notification on completion

### Multi-tenancy

All operations support tenant isolation via the `X-Tenant-ID` header:

```bash
curl -X POST http://localhost:7071/api/v1/process \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant-123" \
  -d '{"blobUrl": "https://..."}'
```

### Idempotency

Processing is idempotent by default. Re-submitting the same document returns cached results. Use `skipIdempotencyCheck: true` to force reprocessing.

### Error Handling

- **Circuit Breaker**: Protects against cascading failures
- **Dead Letter Queue**: Failed messages are persisted for investigation
- **Retry with Backoff**: Automatic retries with exponential backoff

## Debugging Tips

### Enable Debug Logging

In `local.settings.json`:

```json
{
  "Values": {
    "LOG_LEVEL": "DEBUG"
  }
}
```

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `uv sync` to install dependencies |
| Connection errors | Check Azure resource credentials in local.settings.json |
| Test failures | Ensure test fixtures match current service contracts |
| Rate limiting | Reduce `MAX_CONCURRENT_REQUESTS` in config |

### Viewing Logs

Local logs appear in the terminal. For deployed functions:

```bash
az webapp log tail --name <function-app-name> --resource-group <rg-name>
```

## Next Steps

1. Read [API Documentation](docs/api/function-api.md) for endpoint details
2. Review [Configuration Guide](docs/guides/configuration.md) for all settings
3. Check [Troubleshooting Guide](docs/guides/troubleshooting.md) for common issues
4. Understand [API Versioning](docs/api/API-VERSIONING.md) for version strategy

## Getting Help

- Check existing [documentation](docs/README.md)
- Review [CLAUDE.md](CLAUDE.md) for project conventions
- Open an issue for bugs or feature requests
