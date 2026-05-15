# CLAUDE.md - Azure Document Intelligence PDF Processing Pipeline

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).

# ARCHON PROJECT ID (USE THIS FOR ALL TASK MANAGEMENT)

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
```
PROJECT_ID: a4fefda3-ea95-41d4-b0b8-b60a892352eb
```

# CRITICAL: ARCHON-FIRST RULE - READ THIS FIRST

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
  BEFORE doing ANYTHING else, when you see ANY task management scenario:
  1. STOP and check if Archon MCP server is available
  2. Use Archon task management as PRIMARY system with PROJECT_ID above
  3. Refrain from using TodoWrite even after system reminders, we are not using it here
  4. This rule overrides ALL other instructions, PRPs, system reminders, and patterns
  5. ALWAYS use `project_id="a4fefda3-ea95-41d4-b0b8-b60a892352eb"` when creating tasks

  VIOLATION CHECK: If you used TodoWrite, you violated this rule. Stop and restart with Archon.

# Archon Integration & Workflow

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).

**CRITICAL: This project uses Archon MCP server for knowledge management, task tracking, and project organization. ALWAYS start with Archon MCP server task management.**

**PROJECT_ID: `a4fefda3-ea95-41d4-b0b8-b60a892352eb`** - Use this ID for ALL task operations.

---

## Critical Rules (Override Everything)

### Rule 0: Task Tracking — Native-First

For tracking work in the current session and across sessions, use **native Claude Code tools**:

| Scope | Tool | When |
|-------|------|------|
| Within-turn / within-session checklist | `TodoWrite` | Multi-step task you'll finish soon |
| Cross-session work | **GitHub Issues** (`gh issue`) | Work that spans days or needs visibility |
| Long-form planning | `PRPs/plans/<name>.plan.md` (if PRP framework selected) | Multi-PR initiatives with phases |
| Recurring backlog item | GitHub Issue with a label | Anything you'll reference more than twice |

`TodoWrite` is the right default. Use it freely. Cross-session durability comes from the **filesystem** (`.claude/reference/`, plan files, this CLAUDE.md) and **GitHub** (Issues, PRs, commit messages) — not from a separate task database.

### Rule 1: Load Context First

At the start of EVERY session, before any code work:

1. Run the [Startup Protocol](#startup-protocol).
2. Read this `CLAUDE.md` and any relevant `.claude/reference/*.md`.
3. Check `git status` and `git log -10` for in-flight work.
4. Check open GitHub Issues / PRs if relevant: `gh pr list` / `gh issue list`.
5. Check `MEMORY.md` if there's per-project auto-memory at `~/.claude/projects/<slug>/memory/`.

Never start coding without orienting first.

### Rule 2: Preserve Context in the Filesystem

Project knowledge that survives context resets lives in **files**, not in your conversation:

| Document | Where | When to update |
|----------|-------|----------------|
| Architecture decisions | `.claude/reference/architecture.md` | After any architectural decision |
| Deployment runbook | `.claude/reference/deployment.md` | After deployment changes |
| Session handoff | `.claude/reference/session-context.md` | End of each significant session, before `/compact` or `/clear` |
| API surface | `.claude/reference/api.md` (or generated OpenAPI) | After API surface changes |
| Non-obvious facts / gotchas | `MEMORY.md` (auto-memory) | When you hit something a future session needs |

If the context window approaches 70%, update `session-context.md` BEFORE compacting. Load specific reference docs on demand with `@.claude/reference/<file>.md` syntax — don't preload everything.

### Rule 3: Skills Discovery

Before implementing anything non-trivial, check available skills (`.claude/skills/` and `~/.claude/skills/`). Skills are tested, opinionated workflows - prefer them over ad-hoc solutions.

### Rule 4: Temporary Files Go in `temp/`

All temp files MUST be created under `./temp/` (gitignored), never the repo root. Create the directory if it doesn't exist. Never commit temp files.

### Rule 5: Never Tamper with Security Software

This machine may be Intune-managed. Claude must NEVER attempt to disable, stop, or modify Windows Defender, antivirus, or any security software. If a task seems blocked by security, STOP and ask the user - do not work around it.

### Rule 6: Never Read Secrets

Forbidden paths: `.env`, `.env.*`, `secrets/**`, `~/.ssh/**`, `~/.aws/**`, `**/credentials.json`, `**/service-account.json`. Use `.env.example` as a template only.

### Rule 7: Automatic Behaviors Live in Hooks, Not Memory

If you want Claude to "always do X when Y happens" (e.g., run a linter after every edit, post to Slack on session end, validate env vars before deploy), that **must** be a hook in `.claude/settings.json` — not a memory entry or a CLAUDE.md instruction.

| Mechanism | Fires when | Best for |
|-----------|-----------|----------|
| **Hooks** (`settings.json`) | Deterministic events: PreToolUse, PostToolUse, UserPromptSubmit, Stop, etc. | "Always run X after Y" |
| **Memory** (`MEMORY.md`) | Recalled by Claude when relevant context appears | Facts, preferences, prior decisions |
| **CLAUDE.md** | Loaded into every session | Project-wide policies and conventions |
| **Skills** | Auto-invoked when description matches user intent | Reusable workflows |

If your rule says "from now on, when X, do Y" — write a hook. Memory cannot enforce; it only informs.

---

## Project Reference

| Field | Value |
|-------|-------|
| **Project Title** | [PROJECT_TITLE] |
| **GitHub Repo** | [GITHUB_REPO] |
| **Repository Path** | [REPOSITORY_PATH] |
| **Primary Stack** | [PRIMARY_STACK] |

```bash
gh repo view [GITHUB_REPO]              # current state
gh issue list --state open               # in-flight backlog
gh pr list --state open                  # in-flight changes
```

---

## Startup Protocol

Run at the start of EVERY session:

1. **Read this file** + any reference docs the task touches (`@.claude/reference/<topic>.md`).

2. **Check git state**:

   ```bash
   git status
   git log --oneline -10
   ```

3. **Check in-flight GitHub work** (if relevant):

   ```bash
   gh pr list --state open
   gh issue list --state open --assignee @me
   ```

4. **Check `.claude/reference/session-context.md`** if it exists — picks up where the prior session left off.

5. **Brief the user** with: what was being worked on, uncommitted changes, recommended next step.

---

## Project Type: Web Frontend

| Concern | Guidance |
|---------|----------|
| **Verify in browser** | Type checks and tests verify *correctness*, not *features*. Before claiming UI work is done, start the dev server and exercise the change. If you can't reach a browser, say so explicitly. |
| **Hydration boundaries** | Server components stay server-only. Client components are leaf-most. `"use client"` is a cost — push it down, not up. |
| **State management** | Default to URL state and server state. Reach for client-side state libraries only when both fail. |
| **Accessibility** | Semantic HTML first. Test with keyboard navigation before declaring done. |
| **Visual regression** | If Playwright MCP is installed, use it for snapshot diffs on golden flows. |

Don't add CSS frameworks, animation libraries, or state management unless the task requires it.
---

## Code Style

| Principle | Apply to |
|-----------|----------|
| Single responsibility | Functions, classes, modules |
| Readable over clever | Default |
| DRY | Extract after the third repetition, not the second |
| Testable | Pure functions where possible |
| Minimal dependencies | Add only when truly needed |

[PRIMARY_LANGUAGE]-specific conventions: customize this section.

---

## Testing

| Type | Target | Location |
|------|--------|----------|
| Unit | 80%+ on changed code | `tests/unit/` |
| Integration | Critical paths | `tests/integration/` |
| E2E | Happy paths + critical flows | `tests/e2e/` |

AAA pattern: Arrange / Act / Assert. Run tests before marking a task `review`.

---

## Security

Never commit: API keys, passwords, private keys, connection strings, `.env` files.
Use environment variables. The `.env.example` in this repo lists required variables.

Validate user input. Parameterize queries. Sanitize output. Keep deps updated.

---

## Git Workflow

Branches: `feature/<ticket>-desc`, `bugfix/<ticket>-desc`, `hotfix/<ticket>-desc`.

Commit format: `<type>(<scope>): <short summary>` where type is `feat|fix|docs|style|refactor|test|chore|perf`.

PR requirements: clear description, linked issue, tests, CI green.

---

## End of Session Protocol

1. Update `.claude/reference/session-context.md` with: what was completed, decisions made, next steps, blockers.
2. Update or close any open `TodoWrite` items (mark completed as you go, don't batch).
3. Commit uncommitted work with a descriptive message.
4. If the work warrants a follow-up GitHub Issue (something you'll want to find later), open it now: `gh issue create`.
5. Brief the user with a session summary.

Always update `session-context.md` BEFORE `/clear` or `/compact` near 70%.

---

## Available Tools

> Generated by the project wizard from the deployed skills/commands/agents/MCP servers.

### Skills (`.claude/skills/`)

| Skill | Description |
|-------|-------------|
| `prp-core-runner` | Orchestrate complete PRP workflow from feature request to pull request. Run c... |

### Commands (`.claude/commands/`)

| Command | Category |
|---------|----------|
| `/end` | base_commands |
| `/next` | base_commands |
| `/save` | base_commands |
| `/start` | base_commands |
| `/status` | base_commands |

### Agents (`.claude/agents/`)

| Agent | Type |
|-------|------|
| `api-documenter` | Markdown |
| `architect-review` | Markdown |
| `background-researcher` | Markdown |
| `code-simplifier` | Markdown |
| `codebase-analyst` | Markdown |
| `data-engineer` | Markdown |
| `docs-architect` | Markdown |
| `documentation-manager` | Markdown |
| `library-researcher` | Markdown |
| `python-pro` | Markdown |
| `search-specialist` | Markdown |
| `validation-gates` | Markdown |
| `verify-app` | Markdown |

### MCP Servers (`.vscode/mcp.json`)

_No project-specific MCP servers configured. See `.vscode/mcp.json` for active servers._

---

## Claude Code Capabilities Quick Reference

Pointers to features that meaningfully change how a task gets done. Use these when the situation matches — don't reach for them by default.

### Sub-agents and isolation

| When | Tool | Notes |
|------|------|-------|
| Need independent research that would bloat main context | `Agent` with `subagent_type: Explore` or `general-purpose` | Returns a single message; main thread stays clean |
| Need 2+ independent investigations | Multiple `Agent` calls in **one** message | Run in parallel |
| Risky refactor that might fail | `Agent` with `isolation: worktree` | Auto-cleanup if no changes made |
| Specialized work matches an agent | `Agent` with the right `subagent_type` | See agent registry in `.claude/agents/` |

### Background tasks

| When | How |
|------|-----|
| Command runs >5 min (CI watch, large build) | `Bash` with `run_in_background: true` |
| Want notification on completion | The harness notifies automatically — **don't poll** |
| Long agent run that doesn't block your next steps | `Agent` with `run_in_background: true` |

### Context management

| Action | Command / Syntax |
|--------|------------------|
| Check token usage | `/cost` |
| Compress conversation (preserves intent) | `/compact` — update Session Context first if near 70% |
| Hard reset | `/clear` — save context to disk first |
| Load a reference doc on demand | `@.claude/reference/<file>.md` in user prompt |
| Switch model mid-session | `/model opus` / `/model sonnet` / `/model haiku` |
| Faster Opus output | `/fast` (Opus 4.6 / 4.7 only — no quality drop) |

### Permission & settings

| Need | Where |
|------|-------|
| Allow specific commands without prompts | `permissions.allow` in `.claude/settings.json` |
| Per-tool restrictions for a skill/agent | `allowed-tools:` frontmatter |
| Auto-accept edits in current session | `/permissions` → accept edits mode |
| Plan-only mode (read, don't write) | `/permissions` → plan mode |

### Model selection heuristic

| Task type | Default model |
|-----------|---------------|
| Heavy reasoning, architecture, audits | Opus (Opus 4.7 has 1M context) |
| Day-to-day coding, refactors | Sonnet |
| Quick lookups, simple edits, batch ops | Haiku |

### Skill & command frontmatter (modern fields)

```yaml
---
name: my-skill
description: When to use it (matters for auto-invocation)
effort: high              # low|medium|high|max — reasoning depth
context: fork             # Run in isolated subagent
allowed-tools: Read, Grep # Restrict tool access
argument-hint: "[file]"   # Shown in autocomplete
hooks:                    # Skill-scoped hooks
  PostToolUse:
    - matcher: "Edit"
      hooks: [{type: command, command: "./format.sh"}]
---
```

### Memory system

Per-project auto-memory lives in `~/.claude/projects/<project-slug>/memory/`. Index is `MEMORY.md`. Save user/feedback/project/reference notes there — never duplicate facts already in code or git history.

---

## Important Notes

- Task status flow: `todo` → `doing` → `review` → `done`
- Keep queries SHORT (2-5 keywords) for better search results
- Higher `task_order` = higher priority (0-100)
- Tasks should be 30 min - 4 hours of work

## Quick Reference

```bash
# Development

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
uv sync                                    # Install dependencies
cd src/functions && func start             # Run functions locally

# Testing

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
uv run pytest tests/unit/ -v               # Unit tests
uv run pytest tests/unit/ --cov=src        # With coverage

# Linting

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
uv run ruff check src/ tests/              # Lint
uv run ruff format src/ tests/             # Format

# Deploy Infrastructure (subscription-level, creates RG automatically)

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam \
  --parameters sqlAdministratorPassword='YourSecurePassword123!'

# Deploy Function Code

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
cd src/functions && func azure functionapp publish <function-app-name> --python
```

# Azure Document Intelligence PDF Processing Pipeline

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
## Project Overview

Automated document processing pipeline that:
1. **Splits multi-page PDFs** into 2-page form chunks automatically
2. **Extracts data** from PDFs using **Azure Document Intelligence** custom models
3. **Processes forms in parallel** with rate-limit aware concurrency
4. **Orchestrates processing** via **Azure Synapse Analytics**
5. **Persists extracted data** to **Azure Cosmos DB** with PDF source links
6. **Deploys infrastructure** via **Bicep**

### Key Features
- 🔄 **Auto PDF Splitting**: Multi-page PDFs split into 2-page forms
- ⚡ **Parallel Processing**: 3 concurrent Document Intelligence calls
- 📎 **PDF Archive**: Split PDFs stored in `_splits/` for review
- 🔗 **Source Linking**: Each Cosmos DB record links to its processed PDF

**Core Principles**: KISS, YAGNI, DRY, Infrastructure as Code, Fail Fast, Idempotency

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Infrastructure | Azure Bicep |
| Orchestration | Azure Synapse Analytics |
| Processing | Azure Functions (Python 3.10+, v4 runtime) |
| Document AI | Azure Document Intelligence (2024-02-29-preview) |
| Database | Azure Cosmos DB (NoSQL) |
| Storage | Azure Blob Storage |
| Secrets | Azure Key Vault |
| Package Manager | UV |

---

## Project Structure

```
azure-doc-intel-pipeline/
├── infra/
│   ├── main.bicep                       # Main deployment orchestrator (subscription-level)
│   ├── modules/                         # Reusable Bicep modules
│   │   ├── storage.bicep
│   │   ├── document-intelligence.bicep
│   │   ├── cosmos-db.bicep
│   │   ├── synapse.bicep                # Includes GitHub integration
│   │   ├── function-app.bicep
│   │   ├── key-vault.bicep
│   │   ├── log-analytics.bicep
│   │   ├── role-assignment.bicep        # Cross-RG role assignments
│   │   └── private-endpoints.bicep      # Private Endpoints for secure connectivity
│   └── parameters/                      # Environment configs
│       ├── dev.bicepparam               # New deployment (dev)
│       ├── prod.bicepparam              # New deployment (prod)
│       └── existing.bicepparam          # Existing resources mode
├── scripts/
│   └── Deploy-SynapseArtifacts.ps1      # Synapse artifact deployment
├── src/
│   ├── functions/                 # Azure Functions
│   │   ├── function_app.py        # Entry point (PDF splitting, parallel processing)
│   │   ├── config.py              # Configuration management
│   │   ├── services/              # Business logic
│   │   │   ├── document_service.py    # Document Intelligence integration
│   │   │   ├── cosmos_service.py      # Cosmos DB operations
│   │   │   ├── blob_service.py        # Blob storage & SAS tokens
│   │   │   └── pdf_service.py         # PDF splitting with pypdf
│   │   └── requirements.txt
│   └── synapse/                   # Synapse artifacts (singular names)
│       ├── pipeline/              # Pipeline definitions
│       ├── linkedService/         # LS_AzureFunction, LS_AzureBlobStorage, LS_CosmosDB, LS_KeyVault
│       ├── dataset/               # Dataset definitions
│       ├── notebook/              # Spark notebooks (Synapse Link, Delta Lake)
│       └── sqlscript/             # SQL serverless queries
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/                          # Project documentation
│   ├── README.md                  # Documentation index
│   ├── DOCUMENTATION-STANDARDS.md # Visual & writing guidelines
│   ├── guides/                    # How-to guides
│   ├── azure-services/            # Azure service docs
│   └── diagrams/                  # Excalidraw architecture diagrams
└── PRPs/                          # Product Requirement Prompts
```

---

## Code Conventions

### Python

```python
# Always use type hints

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
def process_document(blob_url: str, model_id: str) -> dict[str, Any]:
    """Docstrings for all public functions."""
    pass

# Naming: snake_case variables, SCREAMING_SNAKE constants, PascalCase classes

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
# Max function length: 50 lines (prefer 20-30)

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
# Max file length: 300 lines

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
```

**Error handling pattern:**
```python
class DocumentProcessingError(Exception):
    def __init__(self, blob_name: str, reason: str):
        self.blob_name = blob_name
        self.reason = reason
        super().__init__(f"Failed to process {blob_name}: {reason}")
```

**Config pattern:**
```python
class Config:
    DOC_INTEL_ENDPOINT = os.environ["DOC_INTEL_ENDPOINT"]     # Required
    COSMOS_DATABASE = os.environ.get("COSMOS_DATABASE", "DocumentsDB")  # Optional
```

### Bicep

```bicep
@description('Always include descriptions')
param deploymentMode string = 'new'

var resourceSuffix = '${prefix}-${environment}-${uniqueString(resourceGroup().id)}'

// Always output important values
output storageAccountName string = storage.outputs.name
```

---

## Cosmos DB Document Schema

```json
{
    "id": "folder_document_pdf_form1",
    "sourceFile": "folder/document.pdf",    // Partition key (original PDF)
    "processedPdfUrl": "https://storage.blob.../_splits/document_form1_pages1-2.pdf",
    "processedAt": "2024-01-15T10:30:00Z",
    "formNumber": 1,                        // Which form in the PDF (1-indexed)
    "totalForms": 3,                        // Total forms extracted from PDF
    "pageRange": "1-2",                     // Pages in original PDF
    "originalPageCount": 6,                 // Total pages in original PDF
    "modelId": "custom-model-v1",
    "modelConfidence": 0.95,
    "docType": "invoice",
    "fields": { "vendorName": "Acme Corp", "invoiceTotal": 1500.00 },
    "confidence": { "vendorName": 0.98, "invoiceTotal": 0.95 },
    "status": "completed",
    "error": null
}
```

---

## Critical Gotchas

### Document Intelligence
- **Rate limit**: 15 TPS default - use exponential backoff
- **Async operation**: `begin_analyze_document()` returns poller, call `.result()` to block
- **Large PDFs**: Can take 30+ seconds - set appropriate timeouts

### Cosmos DB
- **Partition key required**: `sourceFile` must be in every document
- **Cross-partition queries expensive**: Always filter by partition key
- **ID uniqueness**: Per partition only - derive from blob path
- **Existing mode auto-creates DB/container**: When using `deploymentMode=existing`, the database and container are automatically created if they don't exist
- **Synapse Link on existing accounts**: Must enable at account level first (Portal), then set `enableExistingCosmosAnalyticalStore=true`

### Synapse
- **Web Activity timeout**: Default 1 min, increase to 10 min for doc processing
- **ForEach limit**: Max 50 parallel, use `batchCount` to control
- **Artifact folder names**: Use SINGULAR names (`linkedService/`, `pipeline/`, `dataset/`, `notebook/`, `sqlscript/`)
- **File names must match resource names**: `LS_AzureFunction.json` must have `"name": "LS_AzureFunction"` inside
- **URL encoding for blob paths**: Filenames with spaces need `encodeUriComponent()` in pipeline expressions

### Function App & Synapse Integration
- **SAS tokens required**: Document Intelligence cannot access private blobs - function generates SAS tokens automatically
- **Storage connection string**: Function uses `AzureWebJobsStorage` to generate SAS tokens
- **Function key authentication**: Synapse must use function key from Key Vault (not managed identity) for HTTP triggers
- **Key Vault linked service**: `LS_KeyVault` must be deployed before `LS_AzureFunction` which references it
- **Secret name**: Function key must be stored as `FunctionAppHostKey` in Key Vault

### Bicep
- **uniqueString()**: Deterministic but short - combine with prefix
- **Storage names**: Must be lowercase, no hyphens, 3-24 chars
- **Conditional outputs**: Check if module deployed before accessing
- **Cross-RG references**: Use `scope: resourceGroup(rgName)` for resources in different RGs
- **Cross-subscription**: Use `scope: resourceGroup(subscriptionId, rgName)` for cross-subscription

### Security Hardening (Infrastructure)
The following Bicep modules support security hardening parameters:

**Storage (`storage.bicep`):**
- `enableNetworkHardening`: Sets `networkAcls.defaultAction` to 'Deny' (default: true for prod)
- `allowedIpRanges`: Array of CIDR ranges for allowed access
- `allowedSubnetIds`: Array of subnet resource IDs for VNet service endpoints

**Key Vault (`key-vault.bicep`):**
- `enableNetworkHardening`: Sets `publicNetworkAccess` to 'Disabled' (default: true for prod)
- `allowedIpRanges`: Array of CIDR ranges for allowed access
- `allowedSubnetIds`: Array of subnet resource IDs

**Cosmos DB (`cosmos-db.bicep`):**
- `enableNetworkHardening`: Sets `publicNetworkAccess` to 'Disabled' and enables VNet filtering (default: true for prod)
- `allowedIpRanges`: Array of CIDR ranges for allowed access (uses `ipRules` property)
- `allowedSubnetIds`: Array of subnet resource IDs for VNet service endpoints

**Function App (`function-app.bicep`):**
- `enableNetworkHardening`: Enables VNet integration (requires non-Consumption plan)
- `vnetIntegrationSubnetId`: Subnet resource ID for outbound VNet integration
- `publicNetworkAccess`: 'Enabled' or 'Disabled' (for Private Endpoint only access)
- `scmAllowedIpRanges`: Array of CIDR ranges allowed for deployment site

**Private Endpoints (`private-endpoints.bicep`):**
Creates Private Endpoints for secure connectivity to Azure services. Parameters:
- `vnetId`: Virtual Network resource ID
- `privateEndpointSubnetId`: Subnet for private endpoints (must have `privateEndpointNetworkPolicies: Disabled`)
- `createPrivateDnsZones`: Create DNS zones (set false if using centralized DNS)
- Resource-specific parameters (provide to create endpoint):
  - Storage: `storageAccountId`, `storageAccountName`
  - Cosmos DB: `cosmosAccountId`, `cosmosAccountName`
  - Key Vault: `keyVaultId`, `keyVaultName`

**Example production deployment:**
```bicep
// In parameters file for production
param enableNetworkHardening = true
param allowedIpRanges = ['203.0.113.0/24']  // Corporate IP range
param allowedSubnetIds = ['/subscriptions/.../subnets/app-subnet']

// For private endpoints (most secure)
module privateEndpoints 'modules/private-endpoints.bicep' = {
  params: {
    vnetId: vnet.id
    privateEndpointSubnetId: peSubnet.id
    storageAccountId: storage.outputs.resourceId
    storageAccountName: storage.outputs.name
    cosmosAccountId: cosmos.outputs.resourceId
    cosmosAccountName: cosmos.outputs.name
    keyVaultId: keyVault.outputs.resourceId
    keyVaultName: keyVault.outputs.name
  }
}
```

---

## Deployment Options

All deployments use **subscription-level deployment** (`az deployment sub create`). The `deploymentMode` parameter controls what gets deployed.

### Deployment Modes
| Mode | Use Case | Parameter File |
|------|----------|----------------|
| `new` | Fresh deployment of all resources | `dev.bicepparam` or `prod.bicepparam` |
| `existing` | Use existing backend, deploy new Function App | `existing.bicepparam` |

### Cross-Resource-Group Support
Existing resources can be in **different resource groups**. Specify RG for each resource:
```bicep
param existingStorageAccountName = 'storage-account'
param existingStorageAccountResourceGroup = 'rg-storage'  // Different RG

param existingCosmosAccountName = 'cosmos-db'
param existingCosmosAccountResourceGroup = 'rg-databases'  // Different RG
```

### Cross-Subscription Log Analytics
Log Analytics can be in a **different subscription** (common for centralized monitoring):
```bicep
param existingLogAnalyticsWorkspaceName = 'central-monitoring'
param existingLogAnalyticsResourceGroup = 'rg-monitoring'
param existingLogAnalyticsSubscriptionId = '12345678-...'  // Different subscription
```

### Deployment Commands
```bash
# New deployment (all resources)

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam \
  --parameters sqlAdministratorPassword='YourSecurePassword123!'

# Existing resources (new Function App)

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters infra/parameters/existing.bicepparam
```

---

## Security Requirements

1. **Never commit secrets** - Use `.gitignore` for `local.settings.json`
2. **Key Vault for all secrets** - API keys, connection strings
3. **Managed Identity preferred** - Over keys where possible
4. **Short-lived SAS tokens** - For blob access
5. **RBAC** - Least-privilege for all service principals

### Federal Compliance (FedRAMP/FISMA)
```bicep
// Government endpoints
var docIntelEndpoint = 'https://${location}.api.cognitive.microsoft.us'
var cosmosEndpoint = 'https://${accountName}.documents.azure.us'

// Authorized regions only
@allowed(['usgovvirginia', 'usgovarizona', 'usgovtexas'])
param location string = 'usgovvirginia'
```

---

## Development Workflows

### Local Development
```bash
# Setup

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
uv venv && uv sync
cp src/functions/local.settings.template.json src/functions/local.settings.json
# Edit local.settings.json with Azure resource details

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).

# Run

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
cd src/functions && func start

# Test endpoint

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
curl -X POST http://localhost:7071/api/process \
  -H "Content-Type: application/json" \
  -d '{"blobUrl": "https://...", "blobName": "test/doc.pdf"}'
```

### Testing
```bash
uv run pytest tests/unit/ -v                           # All unit tests
uv run pytest tests/unit/ --cov=src --cov-report=html  # With coverage
uv run pytest tests/integration/ -v --run-integration  # Integration (needs deployed resources)
```

### Deployment
```bash
# Validate (what-if)

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
az deployment sub what-if \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam \
  --parameters sqlAdministratorPassword='YourSecurePassword123!'

# Deploy infrastructure (creates RG automatically)

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam \
  --parameters sqlAdministratorPassword='YourSecurePassword123!'

# Deploy function code

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
cd src/functions && func azure functionapp publish <function-app-name> --python
```

### Synapse Pipeline
```bash
# Import pipeline

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
az synapse pipeline create \
  --workspace-name <synapse-workspace> \
  --name ProcessPDFsWithDocIntelligence \
  --file @src/synapse/pipelines/process-pdfs-pipeline.json

# Trigger run

> **Note:** This project previously used Archon v1 for task tracking. Archon v1 was archived by its author in April 2026. Historical Archon task records were exported to `.claude/migrated-archon-tasks.md` at migration time. Use TodoWrite + GitHub Issues going forward (see Rule 0).
az synapse pipeline create-run \
  --workspace-name <synapse-workspace> \
  --name ProcessPDFsWithDocIntelligence \
  --parameters sourceFolderPath=incoming
```

---

## Decision Guidelines for Claude Code

### Do Autonomously
- Run linting/formatting before committing changes
- Add type hints to all new Python code
- Write unit tests for new functionality
- Validate Bicep syntax before suggesting infrastructure changes
- Follow existing patterns in codebase

### Ask First
- Significant architectural changes
- New external dependencies
- Changes to deployment modes (new/existing)
- Modifications to security configurations
- Changes affecting federal compliance

### Always
- Check for existing patterns before introducing new ones
- Consider both deployment modes for infrastructure changes
- Update this CLAUDE.md when adding new patterns
- Use PRP methodology for significant new features
- Test locally when possible before suggesting deployments

---

## Optional: Archon RAG

> **Skip this section unless you have a substantial private/internal corpus** that genuinely needs vector search. For library docs (FastAPI, React, Pydantic, etc.), use the `project-kb` skill — it wraps Context7 MCP, which already indexes 1000+ libraries with fresher content than any local corpus.

For projects with extracted internal documentation:

1. Drop markdown files in `.claude/kb/` (gitignored if confidential, committed if public).
2. The `project-kb` skill will grep them automatically.
3. No vector store, no MCP server, no background indexing — just filesystem search with `Grep`.

If you genuinely need vector retrieval (semantic similarity, fuzzy concept matching across a large private corpus), evaluate options like LanceDB-on-disk or a self-hosted Qdrant — but that's a deliberate, scoped infrastructure decision, not a default.

---

