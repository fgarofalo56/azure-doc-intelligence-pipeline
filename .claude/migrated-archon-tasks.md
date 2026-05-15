# Migrated Archon v1 Tasks - Azure Document Intelligence PDF Processing Pipeline

> Frozen export 2026-05-14 during the de-Archon-v1 migration.
> **Archon project ID**: `a4fefda3-ea95-41d4-b0b8-b60a892352eb`
> **Total tasks captured**: 88

Going forward use TodoWrite (in-session) + GitHub Issues (cross-session).

## status: done (88)

### Fix Cosmos DB database/container not found error
_order: 114 . id: `80fb3f7d-9a67-4aec-90c8-8be23d31e285`_

Create the database and container in Cosmos DB or update Function App settings

### Fix pipeline trigger command in notebook
_order: 113 . id: `2305ae9f-578d-4e15-97db-fdd19d474a18`_

Fix the az synapse pipeline create-run command to properly pass JSON parameters on Windows

### Create GitHub Actions CI/CD pipeline
_order: 112 . feature: CI/CD . id: `495cdc53-ac9f-434d-a67f-00e5831ff92c`_

Add .github/workflows/ci.yml with lint, test, coverage, and deploy jobs

### Commit new untracked files to git
_order: 112 . feature: Phase 1: High Priority . id: `9efe1743-45b4-4e34-b532-0ec6779c866c`_

7 new files are untracked: ci.yml, pre-commit-config.yaml, docker-compose.yml, Dockerfile, models.py, telemetry_service.py, webhook_service.py

### Fix security vulnerabilities (URL validation, log sanitization, size limits)
_order: 111 . feature: Security . id: `025da285-d604-4cb7-85b6-b124f9911361`_

Fix critical security issues: 1) Fix invalid URL validation in blob_service.py:69, 2) Strip SAS tokens from logs in document_service.py:143, 3) Add request body size limits in function_app.py, 4) Add path traversal prevention for blob names, 5) Validate webhook URLs

### Add unit tests for new services
_order: 110 . feature: Phase 1: High Priority . id: `701268a6-d3b4-44e1-9fbb-3f16346c7e2c`_

Create tests for telemetry_service.py, webhook_service.py - CI requires 70% coverage threshold

### Make PAGES_PER_FORM configurable via environment variable and request parameter
_order: 109 . feature: Configurable PDF Splitting . id: `408a0543-bffb-4480-ba64-f83b485ec3ac`_

Add pages_per_form to Config dataclass, support PAGES_PER_FORM env var with default of 2, allow per-request override in ProcessRequest model

### Implement Cosmos DB connection pooling
_order: 109 . feature: Performance . id: `8da9d366-a8c9-4d5e-bafc-fd0866b5c0a2`_

Refactor CosmosService to use lazy singleton pattern with connection pooling instead of creating new client per operation. This will improve performance by 10x (100-200ms overhead reduction per operation).

### Add security scanning (bandit) to CI
_order: 108 . feature: Phase 1: High Priority . id: `21be1fb6-a523-47cd-a2af-86da9b114447`_

Add bandit for Python security vulnerability scanning in GitHub Actions pipeline

### Full codebase review with Serena
_order: 107 . feature: Code Quality . id: `d4ad9452-47a0-419d-9318-c7ec515767e0`_

Perform comprehensive codebase review using Serena MCP server. Review all Python code (function_app.py, services/, config.py), Bicep infrastructure (main.bicep, modules/), Synapse artifacts (pipelines, linked services), and tests. Check for code quality, security issues, unused code, and consistency with CLAUDE.md patterns.

### Extract hardcoded constants to Config (semaphore, retries, delays)
_order: 107 . feature: Configuration Enhancement . id: `74b5de42-4838-4aa9-89af-4deaa2739035`_

Move Semaphore(3), max_retries=5, initial_retry_delay=2.0, batch_max_blobs=50 to Config dataclass with env var support

### Add readiness/liveness health probes
_order: 107 . feature: Operational . id: `1f372010-b1b6-40ca-b36e-a78054b0fc62`_

Add Kubernetes-style health endpoints: GET /api/health/live (liveness), GET /api/health/ready (readiness with dependency checks for Cosmos, Storage, Document Intelligence)

### Add Blob Trigger for auto-processing
_order: 106 . feature: Functions . id: `4b0a3829-76ea-45fb-9779-43676843785d`_

Add blob trigger function to auto-process PDFs when uploaded to incoming/

### Add Dependabot configuration
_order: 106 . feature: Phase 1: High Priority . id: `009a9d5d-76a3-4c66-8a88-9f88d78a0b94`_

Create .github/dependabot.yml for automatic dependency updates and security patches

### Implement Processing Profiles for different form types
_order: 105 . feature: Processing Profiles . id: `2bc33e96-899e-487a-b946-0217ba817ef9`_

Create ProcessingProfile dataclass with model_id, pages_per_form, confidence_threshold, required_fields. Add PROFILES registry and ?profile= request parameter support

### Implement circuit breaker pattern
_order: 105 . feature: Reliability . id: `fc2cc3c9-0903-4ef3-b230-81fee89bcd51`_

Add circuit breaker for Document Intelligence API calls to prevent cascading failures. States: CLOSED (normal), OPEN (fast-fail), HALF_OPEN (test recovery)

### Update Bicep for cross-resource-group existing resources
_order: 104 . feature: Infrastructure . id: `331256de-fbd0-4f73-bf3e-fadac68e5f53`_

Modify infra/main.bicep and infra/modules/existing-resources.bicep to support existing resources in different resource groups. Add parameters for resource group names for each existing resource type.

### Add DLQ retry processor timer function
_order: 104 . feature: reliability . id: `c6a13c24-846f-47a0-a46f-090714f6a2a9`_

Create a timer-triggered Azure Function that periodically processes items from the Dead Letter Queue. Should:
- Query DLQ for items ready for retry (based on next_retry_at)
- Apply exponential backoff with max retry limits
- Move permanently failed items to a 'poison' container
- Send webhook notifications for recovered items
- Track retry metrics in telemetry

COMPLETED:
- Added 4 new methods to DeadLetterQueueService: query_ready_for_retry, mark_retry_in_progress, mark_retry_success, mark_retry_failed
- Created DLQRetryProcessor timer function (runs every 15 minutes by default)
- Added 3 new config options: DLQ_RETRY_SCHEDULE, DLQ_RETRY_BATCH_SIZE, DLQ_RETRY_ENABLED
- Added comprehensive unit tests (13 new tests)
- Items are marked ABANDONED when max retries exceeded
- Webhook notifications sent for recovered items

### Add queue-based async processing with status polling
_order: 103 . feature: Queue-Based Processing . id: `567b400b-6160-46f5-8a5e-d71346190d7b`_

Add Storage Queue trigger for background processing, job submission endpoint returns job_id, status polling endpoint GET /status/{job_id}, job state stored in Cosmos

### Add dead letter queue implementation
_order: 103 . feature: Reliability . id: `1cd74e13-9f4e-4f66-80ab-0815554044ab`_

Implement actual dead letter queue using Azure Storage Queue for failed processing items. Include poison message handling, manual retry mechanism, and DLQ monitoring.

### Add GitHub integration support to Synapse workspace
_order: 102 . feature: Infrastructure . id: `0b96a0b7-f485-4ac3-a4c4-461544480128`_

Update infra/modules/synapse.bicep to support optional GitHub repository configuration. Add parameters for GitHub account, repository, collaboration branch, and root folder.

### Harden infrastructure security (Private Endpoints)
_order: 102 . feature: security . id: `5f9b4714-5527-4481-b48b-7558b3a46b91`_

COMPLETED: Infrastructure security hardening with Private Endpoints support.

Changes made:
1. storage.bicep - Added security hardening params (enableNetworkHardening, allowedIpRanges, allowedSubnetIds) with conditional networkAcls
2. key-vault.bicep - Added security hardening params with conditional publicNetworkAccess and networkAcls
3. function-app.bicep - Added VNet integration (enableNetworkHardening, vnetIntegrationSubnetId, publicNetworkAccess, scmAllowedIpRanges)
4. cosmos-db.bicep - Added security hardening params (enableNetworkHardening, allowedIpRanges, allowedSubnetIds) with ipRules and virtualNetworkRules
5. Created NEW private-endpoints.bicep module - Comprehensive Private Endpoint support for Storage (blob), Cosmos DB (Sql), and Key Vault (vault) with optional Private DNS Zones

All Bicep files validated successfully. CLAUDE.md updated with documentation.

### Update all documentation to match current codebase
_order: 101 . feature: Documentation . id: `428eba0d-cfaa-4712-a1b8-72c995be02e0`_

Ensure CLAUDE.md, README.md, and all inline documentation accurately reflects the current codebase. Update API signatures, configuration options, deployment commands, and architecture descriptions. Remove outdated information and add missing documentation for new features (PDF splitting, parallel processing, etc).

### Add field validation layer for extracted data
_order: 101 . feature: Field Validation . id: `9665190c-4d06-4133-8af8-1408bc115bf7`_

Field validation implemented as part of profiles.py - includes FieldValidation class with required, format, range, lookup validation types and ProcessingProfile.validate_result() method

### Refactor process_pdf_internal() into smaller functions
_order: 101 . feature: Code Quality . id: `446fad4c-931e-4f7d-84d0-32268e8ea240`_

Break up the 300+ line process_pdf_internal() into smaller, testable functions: _check_idempotency_and_split(), _process_forms_parallel(), _notify_completion()

### Consolidate Bicep templates into single main.bicep
_order: 100 . feature: Infrastructure . id: `e87243d3-f039-4df9-96b0-a3cd223c607f`_

Merge deploy-function-app-existing.bicep into main.bicep to have a single deployment template that handles all scenarios (new, existing, Option C+). Update parameter files and documentation.

### Support existing Synapse workspace with external GitHub repo
_order: 100 . feature: Infrastructure . id: `f3a16b57-b668-40d4-9a9a-3e9412b8e817`_

Update Option C/C+ to support existing Synapse workspaces that are configured with GitHub integration pointing to a different repository. The deployment script needs to handle cloning/updating an external repo and copying artifacts there.

### Add Cosmos DB Synapse Link with Delta Lake integration
_order: 100 . feature: Analytics . id: `198532f0-7250-4fc6-86b7-03903cf35fbc`_

COMPLETED: Added Cosmos DB Synapse Link configuration, Spark notebooks for querying, SQL serverless queries, and Delta Lake medallion architecture (raw/silver layers). Files created: cosmos-db.bicep updates, Query_CosmosDB_SynapseLink.json notebook, DeltaLake_Medallion_Architecture.json notebook, Query_CosmosDB_Serverless.json SQL script, Query_DeltaLake_Serverless.json SQL script. Updated Deploy-SynapseArtifacts.ps1 to include notebook and sqlscript folders. Updated README with documentation.

### Fix: Generate SAS tokens for Document Intelligence blob access
_order: 100 . feature: Bug Fix . id: `0ea137c9-1908-44a3-bf92-227a02d718f2`_

COMPLETED: Added SAS token generation to Azure Function. Document Intelligence cannot access private blobs without a SAS token. Created blob_service.py to generate SAS tokens, updated config.py to read storage connection string, updated function_app.py to generate SAS before calling Document Intelligence.

### Add Reprocess endpoint
_order: 100 . feature: Functions . id: `1ddadb2e-4ffc-4621-a54b-91ec829bb7bd`_

POST /api/reprocess/{blob_name} to retry failed documents

### Add idempotency keys to prevent duplicate processing
_order: 99 . feature: Idempotency . id: `7792b5a3-8864-461d-9aa9-ed77c850227c`_

Generate idempotency key from blob_name + etag + model_id hash, store in Cosmos document, check before processing, add processingVersion field

### Add audit logging service
_order: 99 . feature: Security . id: `a5e3e7d4-c545-41f8-af43-69b12b7731e3`_

Create audit log service to track user actions: document processing submissions, queries, deletions, configuration changes. Store in Cosmos DB with userId, action, resourceId, timestamp, status.

### Enhance TelemetryService with structured metrics and dimensions
_order: 97 . feature: Telemetry Enhancement . id: `cd4e452b-077c-493b-a9d8-46acac12298e`_

Add track_metric() with dimensions support, add processing metrics (forms_processed, avg_confidence, avg_processing_time), enable dashboard integration

### Add alerting rules to infrastructure
_order: 97 . feature: Operational . id: `79529674-f00b-499e-a65d-c54bc00dfbc0`_

Add Azure Monitor alert rules to Bicep: error rate >5%, response time >30s, CPU >80%, memory >85%, dead letter queue depth, function app restarts

### Add Docker Compose integration tests with emulators
_order: 97 . feature: testing . id: `1a05d125-4850-41f4-b895-235c674426ef`_

COMPLETED: Docker Compose integration tests with Azure emulators.

Changes made:
1. docker-compose.yml - Enhanced with:
   - Azurite (Azure Storage Emulator) with health checks
   - Cosmos DB Linux Emulator with proper configuration
   - Docker profiles (emulators, test, app) for selective startup
   - Usage documentation in comments

2. tests/conftest.py - Added:
   - Emulator connection constants (Azurite connection string, Cosmos emulator endpoint/key)
   - New 'emulator' pytest marker for emulator-based tests
   - pytest_collection_modifyitems updated to handle RUN_EMULATOR_TESTS flag
   - is_emulator_available() helper function
   - Fixtures: azurite_available, cosmos_emulator_available
   - Fixtures: azurite_blob_service, azurite_test_container
   - Fixtures: cosmos_emulator_service (with SSL verification disabled for emulator)
   - Fixtures: emulator_test_id, emulator_source_file

3. tests/integration/test_blob_emulator.py - NEW: 11 emulator tests
   - TestBlobEmulatorBasicOp...

### Create Synapse artifact deployment script for GitHub workflows
_order: 96 . feature: Deployment . id: `6f94f648-4fdd-403c-816f-99efed79ec81`_

Create PowerShell/Bash scripts to deploy Synapse artifacts. Handle both direct deployment (non-GitHub) and GitHub-based deployment (commit to collaboration branch).

### Create visual documentation standards with icons and graphics
_order: 95 . feature: Documentation . id: `c68d0e2c-9a1f-4b21-a932-aaaafdfd3f4f`_

Establish documentation visual standards using icons, images, and graphics. Create templates with emoji icons for sections (📦 Installation, 🚀 Deployment, ⚙️ Configuration, etc). Add badges, status indicators, and visual hierarchy. Make this the standard for all project documentation going forward.

### Add smart form boundary detection for variable-length forms
_order: 95 . feature: Smart Form Detection . id: `a9869a6c-fc61-42ed-a2d7-68b926a8a795`_

Add detect_form_boundaries() to PdfService using page similarity analysis and header/footer pattern recognition. Support auto mode alongside fixed pages_per_form

### Create ONBOARDING.md and API versioning documentation
_order: 95 . feature: Documentation . id: `37b5d548-92d5-49f7-80e5-43c451492e2e`_

Create /ONBOARDING.md with step-by-step new developer setup guide and /docs/api/API-VERSIONING.md explaining version strategy, deprecation policy, and migration paths

### Add Application Insights custom metrics
_order: 94 . feature: Observability . id: `87533a97-854f-4855-b6e2-4e2467ebabca`_

Track forms processed, confidence scores, processing duration

### Add resource group creation for new Function App with existing backend
_order: 93 . feature: Infrastructure . id: `7177d6b5-44e9-43b0-8454-7f49a7b2ce01`_

Add support for creating a new resource group when deploying Function App infrastructure with existing backend resources (Option C deployment).

### Add multi-tenant support with tenant isolation
_order: 93 . feature: Multi-Tenant . id: `ae28ec7e-2183-42ba-866b-5c35d76877da`_

Implemented multi-tenant support with: tenantId field in documents, tenant-scoped query endpoint (GET /api/tenants/{tenant_id}/documents), MULTI_TENANT_ENABLED and DEFAULT_TENANT_ID config settings, tenant support in process, batch, and async job endpoints

### Add webhook HMAC signing and retry jitter
_order: 93 . feature: Reliability . id: `04d82812-81c6-43a2-8518-d6074a5e5969`_

Enhance webhook service: 1) Add HMAC-SHA256 signing for payload verification, 2) Add jitter to retry backoff, 3) Persist failed deliveries to Cosmos DB

### Add unit tests for all new enhancement features
_order: 91 . feature: Testing . id: `1392be9c-7818-46a9-9a23-9b71aa32baeb`_

Write comprehensive tests for configurable splitting, profiles, validation, idempotency, queue processing. Maintain 90%+ coverage

### Extract shared URL parsing utility and fix DRY violations
_order: 91 . feature: Code Quality . id: `4f504aa7-2ba0-47b2-9ea4-cfb4841803cb`_

Extract blob URL parsing logic to single _parse_blob_components() utility. Currently duplicated in 6+ locations across blob_service.py and function_app.py

### Create Azure Monitor Workbook dashboard
_order: 91 . feature: monitoring . id: `6b60a7bc-cb67-409c-96c3-28ff50b18f57`_

Add monitoring dashboard infrastructure and configuration:
- Create monitor-workbook.bicep module with Azure Workbook
- Include visualizations for: processing throughput, error rates by type, DLQ depth, circuit breaker states, latency percentiles
- Add KQL queries for common operational scenarios
- Link to existing alert rules
- Export workbook template as JSON for version control

### Update parameter files with Synapse GitHub configuration
_order: 90 . feature: Infrastructure . id: `7230d070-d6cf-419c-b050-1b18d980898e`_

Add GitHub configuration parameters to dev.bicepparam, prod.bicepparam, and existing.bicepparam for Synapse workspace GitHub integration.

### Create extensive project documentation (docs/ folder)
_order: 89 . feature: Documentation . id: `05428c09-f9a8-4dc5-bac8-16934eb724f3`_

Create comprehensive docs/ folder with detailed documentation: Architecture Overview, API Reference, Configuration Guide, Troubleshooting Guide, Development Guide, Deployment Scenarios, Security Considerations. Include code examples, diagrams, and step-by-step instructions.

### Add comprehensive unit tests for new features
_order: 89 . feature: Testing . id: `d2e6a468-14c0-4612-a67d-944072646fd6`_

Write unit tests for all new features: circuit breaker, dead letter queue, audit logging, health probes, webhook HMAC. Target 90%+ coverage.

### Add pre-commit hooks configuration
_order: 88 . feature: DevEx . id: `72fa893f-a9a2-48d2-bb41-83ea589032ec`_

Add .pre-commit-config.yaml with ruff, mypy, bicep linting

### Add API rate limiting
_order: 88 . feature: Phase 2: Medium Priority . id: `be1a69f2-ccf2-4dc8-82cd-9c073e3788ad`_

Protect endpoints from abuse, especially the reprocess endpoint. Consider using Azure API Management or custom middleware.

### Add request validation middleware
_order: 86 . feature: Phase 2: Medium Priority . id: `e5ebba0f-cd03-4e36-aa5a-378d630f321a`_

Centralize input validation using Pydantic models across all endpoints

### Add OpenAPI/Swagger documentation endpoint
_order: 85 . feature: documentation . id: `53e4e98c-0613-407e-8dd2-9603e658d057`_

Generate and serve API documentation:
- Created openapi.yaml specification file documenting all endpoints
- Added GET /api/docs endpoint serving Swagger UI
- Added GET /api/openapi.yaml endpoint for raw OpenAPI spec
- Included request/response schemas from models.py
- Documented authentication methods (Function keys)
- Added examples for common use cases

### Add health check for blob trigger
_order: 84 . feature: Phase 2: Medium Priority . id: `e375e666-c8a7-4ed1-811d-86608f1988a7`_

Monitor blob trigger health separately from HTTP endpoints - detect storage connectivity issues

### Create Excalidraw architecture diagrams
_order: 83 . feature: Documentation . id: `4ab77bea-5c30-49db-a41a-3643ac6eeec4`_

Create comprehensive architecture diagrams using Excalidraw (https://github.com/excalidraw/excalidraw, https://docs.excalidraw.com/docs). Include: System Architecture (all Azure services), Data Flow Diagram, PDF Processing Pipeline, Deployment Architecture, Synapse Pipeline Flow, Infrastructure Components. Export as .excalidraw files and PNG/SVG for documentation.

### Support cross-subscription Log Analytics workspace
_order: 82 . feature: Infrastructure . id: `9a9bbc36-b6e5-41fd-a831-4803b9811c27`_

Update Bicep to support referencing Log Analytics workspaces in different subscriptions. Add subscription ID parameter for existing Log Analytics workspace.

### Add Pydantic models for API contracts
_order: 82 . feature: Functions . id: `5b5c5010-22ac-4e7c-af2f-854a6ba3ae46`_

Create request/response models with validation

### Implement structured JSON logging
_order: 82 . feature: Phase 2: Medium Priority . id: `a045d102-b5ce-4e63-88f3-1fb2f06c291c`_

Convert logs to JSON format for better parsing in Log Analytics and easier querying

### Apply request validation middleware to endpoints
_order: 79 . feature: security . id: `27e99724-265e-4fac-94bc-5b53328e4b35`_

Documented authentication strategy and middleware usage:
- Azure Functions built-in auth (AuthLevel.FUNCTION) is primary auth mechanism
- Documented rate limiting configuration and response headers
- Added authentication strategy section to API-VERSIONING.md
- Clarified middleware decorator usage (validate_request, rate_limit, require_auth)
- Added security best practices
- Middleware is available for enhanced scenarios but not required for basic auth

### Document all required Azure services
_order: 77 . feature: Documentation . id: `f44c8709-e059-4dba-a398-905b909299e3`_

Create comprehensive Azure Services documentation covering all required services: Azure Functions, Document Intelligence, Cosmos DB, Blob Storage, Key Vault, Synapse Analytics, Log Analytics, App Insights. Include: purpose, configuration, pricing tiers, SKU recommendations, networking requirements, security settings, and inter-service connections.

### Add Dockerfile for containerized deployment
_order: 76 . feature: DevEx . id: `6d100072-4034-4d53-8317-e5a96eea806c`_

Support local dev in containers and Azure Container Apps

### Push test coverage to 90%
_order: 75 . feature: Testing . id: `0bc35d73-b098-4a5f-a08f-c64382d38f70`_

Coverage improved from 83% to 93%. Added comprehensive tests for document_service.py (59%→98%), telemetry_service.py (45%→74%), and function_app.py error handlers (87%). Target of 90% exceeded.

### Increase test coverage to 80%
_order: 74 . feature: Testing . id: `865c4316-c002-4787-8ae8-5e4690ceafcd`_

Current coverage is 70.15%. Target 80% by adding tests for: document_service.py (58%), telemetry_service.py (45%), and function_app.py (31%). Focus on high-value code paths.

### Add graceful shutdown handling for long operations
_order: 73 . feature: reliability . id: `ca21735f-455b-498f-8179-05dff6d3b880`_

Implement graceful shutdown for long-running document processing:
- Add signal handlers for SIGTERM/SIGINT
- Implement checkpoint-based progress saving for multi-form PDFs
- Allow resumption of interrupted processing jobs
- Add shutdown timeout configuration
- Update job service to mark interrupted jobs appropriately

### Update existing.bicepparam with new cross-RG parameters
_order: 71 . feature: Infrastructure . id: `01bb0ba7-252f-4dbd-922b-b22efe1014ea`_

Update infra/parameters/existing.bicepparam to include all new parameters for cross-resource-group and cross-subscription support.

### Create Azure Document Intelligence custom model documentation
_order: 71 . feature: Documentation . id: `6f71a40c-f31e-4981-ba69-d68ee98c0075`_

Create detailed documentation on Azure Document Intelligence custom extraction models: What are custom models, When to use them vs prebuilt, Training requirements, Labeling best practices, Model versioning, API usage patterns, Confidence thresholds, Error handling. Include comparison of model types (template vs neural).

### Fix failing unit tests (8 tests)
_order: 71 . feature: Testing . id: `6b74ad93-f326-4980-be8a-f127ad7eafe7`_

8 unit tests are failing due to missing mocks for environment variables and service configuration:

**Failing tests:**
- test_process_document_success
- test_process_document_rate_limit_error
- test_process_document_processing_error
- test_process_document_cosmos_error
- test_process_document_uses_default_model
- test_health_check
- test_track_form_processed_disabled
- test_send_notification_no_url

**Root cause:** Tests need proper mocking for:
- Environment variables (DOC_INTEL_ENDPOINT, COSMOS_ENDPOINT, etc.)
- Service initialization (blob_service, cosmos_service)
- Logging capture configuration

### Add Batch Status endpoint
_order: 70 . feature: Functions . id: `89b19c54-144b-4ba0-ab49-75a7b3277dea`_

GET /api/status/batch/{sourceFile} - get all forms from a multi-page PDF

### Add integration tests for Azure services
_order: 68 . feature: Testing . id: `e3e8a940-a150-4d37-9668-b44896f60d11`_

Create integration tests that run against real Azure services (Document Intelligence, Cosmos DB, Blob Storage). Use pytest markers to separate from unit tests. Requires Azure credentials in CI.

### Add startup configuration validation (fail-fast)
_order: 67 . feature: developer-experience . id: `eef09cc3-50e2-4464-8369-8f8f9312ce2f`_

Validate configuration at application startup:
- Add validate_config() function in config.py
- Check required environment variables early
- Validate endpoint URLs are well-formed
- Verify numeric config values are in expected ranges
- Log clear error messages for missing/invalid config
- Call validation during Function App initialization

### Create Document Intelligence Studio walkthrough guide
_order: 65 . feature: Documentation . id: `af95434f-edf2-4efd-9b40-0056635bbd25`_

Create step-by-step walkthrough for Document Intelligence Studio aligned with this codebase: Setting up a project, Uploading training documents, Labeling fields, Training custom models, Testing models, Deploying models, Copying model IDs to use in pipeline. Include screenshots/descriptions of each step and tips for optimal results.

### Add Delete/Cleanup endpoint
_order: 64 . feature: Functions . id: `db48426e-be31-40f5-8e03-17adbd44456e`_

DELETE /api/documents/{blob_name} - remove processed docs and split PDFs

### Add OpenAPI/Swagger documentation
_order: 64 . feature: Phase 3: Low Priority . id: `2d4db0aa-c9a3-4156-a90e-c04e8b18e338`_

Auto-generate API documentation from Pydantic models for developer reference

### Implement Service Bus retry queue
_order: 62 . feature: Phase 3: Low Priority . id: `9ce20d70-1957-4810-81e5-dc856eb9936e`_

Service Bus retry queue is an infrastructure enhancement that would require adding Azure Service Bus to the Bicep templates. The current blob-based dead letter queue provides basic retry functionality. For production use with high volume, consider adding Service Bus infrastructure.

### Create shared test fixture factories
_order: 61 . feature: testing . id: `1ca22ae6-73b2-47ed-a9d4-418becf075df`_

Create reusable mock factories for consistent testing:
- Add tests/fixtures/ directory with mock factories
- Create MockBlobService, MockCosmosService, MockDocumentService factories
- Add helper functions for creating test documents, PDFs, responses
- Standardize mock patterns across all unit tests
- Document fixture usage in tests/README.md

### Update documentation for cross-RG deployments
_order: 60 . feature: Documentation . id: `ac572db3-96ec-460e-a056-ce3bb42411ca`_

Update CLAUDE.md and README.md with new deployment options, parameters, and examples for cross-resource-group and cross-subscription scenarios.

### Add multi-model support per PDF
_order: 60 . feature: Phase 3: Low Priority . id: `bc8d6122-b490-41ec-9a08-4ddc39f4b4bf`_

Support different Document Intelligence models for different page types within a single PDF

### Improve test coverage to 70%
_order: 60 . feature: Testing . id: `b3fb4e4a-8684-48be-a021-eaa96258807b`_

Test coverage improved from 34% to 70.15%. Added comprehensive test files for: rate_limiter.py (100%), logging_service.py (100%), services/__init__.py (100%), config.py (100%), webhook_service.py (100%). Extended cosmos_service tests to 90%. 237 tests passing.

### Add Dead Letter Queue handling
_order: 58 . feature: Functions . id: `10ff38e3-d99a-4543-b3d6-729dd9221985`_

Move repeatedly failing docs to _dead_letter/ container

### Add batch processing endpoint
_order: 58 . feature: Phase 3: Low Priority . id: `287066ac-ee5a-4bd2-a8dc-911835368115`_

Process multiple PDFs in a single API request for bulk operations

### Add caching layer for Document Intelligence results
_order: 57 . feature: Performance . id: `518c5cf7-6aad-4109-b522-113788fb98d6`_

Cache extraction results in Redis or Cosmos DB to avoid reprocessing identical documents. Use content hash as cache key. Add cache invalidation strategy.

### Add cost estimation endpoint
_order: 56 . feature: Phase 3: Low Priority . id: `cd3f637e-583b-4902-9b47-3a8e24cca0fb`_

Estimate Document Intelligence processing costs before running extraction

### Add Cosmos DB backup/DR configuration to Bicep
_order: 55 . feature: infrastructure . id: `2599c81d-7ff4-48e7-a908-2104955f9070`_

Add disaster recovery infrastructure options:
- Add backup policy parameters to cosmos-db.bicep (continuous vs periodic)
- Add geo-replication option for production
- Configure point-in-time restore settings
- Add backup retention period configuration
- Document DR procedures in docs/guides/disaster-recovery.md

### Add Model Validation
_order: 52 . feature: Functions . id: `9805da6a-a63f-45ba-9348-ca9d626a5a22`_

Pre-check that Document Intelligence model exists before processing

### Add Azure Monitor workbook for pipeline dashboards
_order: 51 . feature: Observability . id: `a4f1a9b5-40ed-43e0-a847-1b735c43e466`_

Create Azure Monitor workbook with dashboards: processing throughput, error rates, Document Intelligence latency, Cosmos DB RU consumption, and cost tracking.

### Add Webhook Notifications
_order: 46 . feature: Functions . id: `e7ca49a9-9dad-4786-a2d0-6a815a7fb71a`_

POST callback when processing completes for downstream systems

### Add API versioning support
_order: 45 . feature: API . id: `43b2de27-11d6-438a-bd84-5bc440e6ec2f`_

Implement API versioning (v1, v2) to allow backwards-compatible changes. Use URL path versioning (/api/v1/process). Add deprecation headers for old versions.

### Update README with new features
_order: 40 . feature: Documentation . id: `0f9aadd6-f000-4646-8a61-e4be92ef30fc`_

Document all new endpoints, CI/CD, Docker, and configuration
