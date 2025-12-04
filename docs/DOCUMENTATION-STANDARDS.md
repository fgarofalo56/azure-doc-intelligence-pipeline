# 📋 Documentation Standards

> **Visual documentation guidelines for the Azure Document Intelligence Pipeline project**

---

## 🎨 Visual Standards

This project uses consistent visual elements to make documentation clear, scannable, and professional.

### Emoji Icons by Section Type

| Section Type | Icon | Usage |
|--------------|------|-------|
| Overview/Introduction | 🎯 | Main purpose statements |
| Installation/Setup | 📦 | Package/dependency sections |
| Configuration | ⚙️ | Settings and environment variables |
| Deployment | 🚀 | Deployment instructions |
| Security | 🔐 | Security-related content |
| Database | 🗄️ | Database schemas and queries |
| API/Integration | 🔌 | API endpoints and integrations |
| Monitoring | 📊 | Logging, metrics, observability |
| Troubleshooting | 🔧 | Problem-solving guides |
| Best Practices | 🏆 | Recommendations |
| Warning/Caution | ⚠️ | Important gotchas |
| Tips | 💡 | Helpful suggestions |
| Code | 💻 | Code examples |
| Files/Folders | 📁 | File structure |
| Resources/Links | 📚 | External references |
| Table of Contents | 📑 | Navigation |

### Azure Service Icons

| Service | Icon | Color Code |
|---------|------|------------|
| Azure Functions | ⚡ | #F59E0B (Orange) |
| Document Intelligence | 🤖 | #DC2626 (Red) |
| Cosmos DB | 🗄️ | #059669 (Green) |
| Blob Storage | 📦 | #0078D4 (Blue) |
| Key Vault | 🔐 | #6B7280 (Gray) |
| Synapse Analytics | 🔄 | #7C3AED (Purple) |
| Log Analytics | 📊 | #0EA5E9 (Cyan) |
| Application Insights | 📈 | #0EA5E9 (Cyan) |

---

## 📝 Markdown Formatting

### Headers

```markdown
# 🎯 Main Title (H1 - only one per document)

## 📑 Major Section (H2)

### Subsection (H3)

#### Detail Section (H4)
```

### Tables

Always use tables for:
- Configuration options
- Comparisons
- Feature lists
- Status indicators

```markdown
| Feature | Status | Notes |
|---------|--------|-------|
| PDF Splitting | ✅ | Automatic 2-page chunks |
| Parallel Processing | ✅ | 3 concurrent forms |
| Custom Models | ✅ | Neural model support |
```

### Status Indicators

| Indicator | Meaning |
|-----------|---------|
| ✅ | Complete/Supported/Yes |
| ❌ | Not supported/No |
| ⚠️ | Warning/Caution |
| 🔄 | In progress |
| 📌 | Important/Pinned |
| 🆕 | New feature |
| 🔜 | Coming soon |

### Code Blocks

Always specify language for syntax highlighting:

````markdown
```python
def process_document(blob_url: str) -> dict:
    """Process a PDF document."""
    pass
```

```bash
# Deploy command
az deployment sub create --location eastus
```

```json
{
  "setting": "value"
}
```
````

### Callouts (Blockquotes)

Use for important information:

```markdown
> **Note:** Important information here

> ⚠️ **Warning:** Critical gotcha or caution

> 💡 **Tip:** Helpful suggestion
```

---

## 📁 Documentation Structure

### Required Files

```
docs/
├── README.md                    # Documentation index
├── DOCUMENTATION-STANDARDS.md   # This file
├── guides/
│   ├── getting-started.md       # Quick start guide
│   ├── deployment.md            # Deployment guide
│   ├── configuration.md         # Configuration reference
│   └── troubleshooting.md       # Troubleshooting guide
├── azure-services/
│   ├── README.md                # Services overview
│   └── [service-name].md        # Per-service docs
├── diagrams/
│   ├── architecture.excalidraw  # Main architecture
│   └── *.png                    # Exported images
└── api/
    └── function-api.md          # API documentation
```

### File Naming

| Type | Convention | Example |
|------|------------|---------|
| Guides | `kebab-case.md` | `getting-started.md` |
| Services | `service-name.md` | `cosmos-db.md` |
| Diagrams | `diagram-name.excalidraw` | `architecture.excalidraw` |
| Standards | `SCREAMING-KEBAB.md` | `DOCUMENTATION-STANDARDS.md` |

---

## 📊 Diagram Standards

### Excalidraw Conventions

**Color Scheme:**

| Element | Color | Hex Code |
|---------|-------|----------|
| Storage | Blue | `#deebff` / `#0078D4` |
| Compute | Orange | `#fef3c7` / `#F59E0B` |
| AI Services | Red | `#fee2e2` / `#DC2626` |
| Database | Green | `#d1fae5` / `#059669` |
| Security | Gray | `#f3f4f6` / `#6B7280` |
| Orchestration | Purple | `#ede9fe` / `#7C3AED` |
| Monitoring | Cyan | `#e0f2fe` / `#0EA5E9` |

**Arrow Conventions:**

| Style | Meaning |
|-------|---------|
| Solid line | Data flow |
| Dashed line | Configuration/secrets |
| Thick line | Primary flow |
| Thin line | Secondary flow |

**Export Requirements:**

1. Export as `.excalidraw` (source)
2. Export as `.png` with embedded scene data
3. Use 2x resolution for clarity
4. Include in git commits

---

## ✍️ Writing Style

### Tone

- **Professional** but approachable
- **Concise** - avoid unnecessary words
- **Action-oriented** - use imperative mood for instructions
- **Consistent** - use same terms throughout

### Voice

| ✅ Do | ❌ Don't |
|-------|---------|
| "Run the following command" | "You should run this command" |
| "Configure the settings" | "The settings should be configured" |
| "The function processes PDFs" | "PDFs are processed by the function" |

### Technical Terms

- Use consistent terminology
- Define acronyms on first use
- Link to glossary for complex terms

| Term | Definition |
|------|------------|
| **MI** | Managed Identity |
| **SAS** | Shared Access Signature |
| **RU/s** | Request Units per second |
| **TPS** | Transactions Per Second |

---

## 🔄 Maintenance

### Update Checklist

When updating documentation:

- [ ] Update relevant diagrams
- [ ] Check all code examples still work
- [ ] Update version numbers
- [ ] Verify links are not broken
- [ ] Update "Last Updated" date
- [ ] Review for consistency with standards

### Version Footer

Every document should end with:

```markdown
---

*Last Updated: [Month Year]*
*API Version: [version]*
```

---

## 📚 Templates

### New Guide Template

```markdown
# 🎯 [Guide Title]

> **[One-line description of what this guide covers]**

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Prerequisites](#-prerequisites)
- [Steps](#-steps)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Overview

[Brief description of the topic]

## 📦 Prerequisites

- [ ] Prerequisite 1
- [ ] Prerequisite 2

## 🚀 Steps

### Step 1: [Action]

[Instructions]

### Step 2: [Action]

[Instructions]

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| [Problem] | [Fix] |

---

*Last Updated: [Month Year]*
```

### New Service Doc Template

```markdown
# [Icon] [Service Name]

> **[One-line purpose statement]**

---

## 📑 Table of Contents

- [Purpose](#-purpose)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Best Practices](#-best-practices)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Purpose

[Why this service is used in the project]

## ⚙️ Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| [Setting] | [Value] | [Notes] |

## 💻 Usage

```python
# Code example
```

## 🏆 Best Practices

- Best practice 1
- Best practice 2

## 🔧 Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| [Issue] | [Cause] | [Solution] |

---

*Last Updated: [Month Year]*
```

---

*Last Updated: December 2024*
