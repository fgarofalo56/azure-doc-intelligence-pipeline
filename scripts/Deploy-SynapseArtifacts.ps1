<#
.SYNOPSIS
    Deploy Synapse artifacts to Azure Synapse workspace or GitHub repository.

.DESCRIPTION
    This script handles deployment of Synapse artifacts (pipelines, linked services, datasets)
    to either:
    1. Direct deployment to Synapse workspace (when GitHub integration is not enabled)
    2. GitHub-based deployment to THIS repository (when Synapse uses this repo)
    3. External GitHub repository deployment (when Synapse uses a DIFFERENT repo)

.PARAMETER WorkspaceName
    Name of the Synapse workspace.

.PARAMETER ResourceGroup
    Resource group containing the Synapse workspace.

.PARAMETER SubscriptionId
    Azure subscription ID (optional, uses current context if not specified).

.PARAMETER ArtifactsPath
    Path to the Synapse artifacts folder in THIS project (default: src/synapse).

.PARAMETER DeploymentMode
    Deployment mode:
    - 'direct': Deploy directly to Synapse workspace (no GitHub integration)
    - 'github': Commit to THIS repository's collaboration branch
    - 'external-github': Clone external repo, copy artifacts, commit and push

.PARAMETER GitHubBranch
    GitHub branch to commit to (default: main).

.PARAMETER CommitMessage
    Commit message for GitHub deployment.

.PARAMETER ExternalRepoUrl
    URL of the external GitHub repository (for 'external-github' mode).
    Example: https://github.com/your-org/synapse-artifacts.git

.PARAMETER ExternalRepoRootFolder
    Root folder in external repository for Synapse artifacts (default: /).
    Example: /synapse or /src/synapse

.PARAMETER StorageAccountUrl
    Storage account blob endpoint URL (for parameter substitution).

.PARAMETER FunctionAppUrl
    Function App URL (for parameter substitution).

.PARAMETER CosmosEndpoint
    Cosmos DB endpoint URL (for parameter substitution).

.PARAMETER CleanupTempFolder
    Whether to cleanup temporary folder after external repo deployment (default: true).

.EXAMPLE
    # Direct deployment to Synapse (no GitHub integration)
    .\Deploy-SynapseArtifacts.ps1 -WorkspaceName "docproc-syn-dev" -ResourceGroup "rg-docprocessing-dev" `
        -DeploymentMode direct -StorageAccountUrl "https://mystorageaccount.blob.core.windows.net"

.EXAMPLE
    # GitHub-based deployment (Synapse configured with THIS repo)
    .\Deploy-SynapseArtifacts.ps1 -WorkspaceName "docproc-syn-dev" -ResourceGroup "rg-docprocessing-dev" `
        -DeploymentMode github -GitHubBranch "main" -CommitMessage "Update pipeline configuration"

.EXAMPLE
    # External GitHub repo deployment (Synapse configured with a DIFFERENT repo)
    .\Deploy-SynapseArtifacts.ps1 -WorkspaceName "docproc-syn-dev" -ResourceGroup "rg-docprocessing-dev" `
        -DeploymentMode external-github `
        -ExternalRepoUrl "https://github.com/your-org/synapse-artifacts.git" `
        -ExternalRepoRootFolder "/synapse" `
        -GitHubBranch "main" `
        -StorageAccountUrl "https://mystorageaccount.blob.core.windows.net" `
        -FunctionAppUrl "https://docproc-func-dev.azurewebsites.net"

.NOTES
    Requires:
    - Azure CLI (az) installed and logged in
    - Git installed and configured with appropriate permissions
    - For external-github mode: Push access to the external repository
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceName,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $false)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $false)]
    [string]$ArtifactsPath = "src/synapse",

    [Parameter(Mandatory = $true)]
    [ValidateSet('direct', 'github', 'external-github')]
    [string]$DeploymentMode,

    [Parameter(Mandatory = $false)]
    [string]$GitHubBranch = "main",

    [Parameter(Mandatory = $false)]
    [string]$CommitMessage = "Deploy Synapse artifacts",

    [Parameter(Mandatory = $false)]
    [string]$ExternalRepoUrl = "",

    [Parameter(Mandatory = $false)]
    [string]$ExternalRepoRootFolder = "/",

    [Parameter(Mandatory = $false)]
    [string]$StorageAccountUrl = "",

    [Parameter(Mandatory = $false)]
    [string]$FunctionAppUrl = "",

    [Parameter(Mandatory = $false)]
    [string]$CosmosEndpoint = "",

    [Parameter(Mandatory = $false)]
    [string]$KeyVaultUrl = "",

    [Parameter(Mandatory = $false)]
    [bool]$CleanupTempFolder = $true
)

$ErrorActionPreference = "Stop"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Get-RepoRoot {
    $gitRoot = git rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -ne 0) {
        # Not in a git repo - return null and let caller handle it
        return $null
    }
    return $gitRoot
}

function Replace-Placeholders {
    param(
        [string]$Content,
        [hashtable]$Replacements
    )

    foreach ($key in $Replacements.Keys) {
        if ($Replacements[$key]) {
            $Content = $Content -replace $key, $Replacements[$key]
        }
    }
    return $Content
}

function Copy-ArtifactsWithSubstitution {
    param(
        [string]$SourcePath,
        [string]$DestinationPath,
        [hashtable]$Replacements
    )

    Write-Info "Source path: $SourcePath"
    Write-Info "Destination path: $DestinationPath"

    # Ensure destination exists
    if (-not (Test-Path $DestinationPath)) {
        Write-Info "Creating destination directory..."
        New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    }

    # Copy and process each subfolder (Synapse uses singular names)
    $subfolders = @("linkedService", "dataset", "pipeline", "notebook", "sqlscript")
    $totalFilesCopied = 0

    foreach ($subfolder in $subfolders) {
        $srcFolder = Join-Path $SourcePath $subfolder
        $destFolder = Join-Path $DestinationPath $subfolder

        Write-Info "  Checking subfolder: $subfolder"
        Write-Info "    Source: $srcFolder"

        if (Test-Path $srcFolder) {
            Write-Info "    [FOUND] Processing $subfolder..."

            if (-not (Test-Path $destFolder)) {
                Write-Info "    Creating destination subfolder: $destFolder"
                New-Item -ItemType Directory -Path $destFolder -Force | Out-Null
            }

            $jsonFiles = Get-ChildItem -Path $srcFolder -Filter "*.json"
            Write-Info "    Found $($jsonFiles.Count) JSON file(s)"

            foreach ($jsonFile in $jsonFiles) {
                $content = Get-Content $jsonFile.FullName -Raw
                $newContent = Replace-Placeholders -Content $content -Replacements $Replacements

                $destFile = Join-Path $destFolder $jsonFile.Name
                $newContent | Out-File -FilePath $destFile -Encoding utf8 -NoNewline
                Write-Success "    Copied: $($jsonFile.Name) -> $destFile"
                $totalFilesCopied++
            }
        } else {
            Write-Warn "    [NOT FOUND] Skipping $subfolder - source folder does not exist"
        }
    }

    Write-Info "Total files copied: $totalFilesCopied"
    return $totalFilesCopied
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

Write-Info "Starting Synapse artifact deployment..."
Write-Info "Workspace: $WorkspaceName"
Write-Info "Resource Group: $ResourceGroup"
Write-Info "Deployment Mode: $DeploymentMode"

# Set subscription if provided
if ($SubscriptionId) {
    Write-Info "Setting subscription to: $SubscriptionId"
    az account set --subscription $SubscriptionId
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to set subscription"
        exit 1
    }
}

# Get repository root or use current directory
$repoRoot = Get-RepoRoot

if ($repoRoot) {
    $artifactsFullPath = Join-Path $repoRoot $ArtifactsPath
} else {
    # Not in a git repo - check if ArtifactsPath is absolute or relative to current directory
    if ([System.IO.Path]::IsPathRooted($ArtifactsPath)) {
        $artifactsFullPath = $ArtifactsPath
    } else {
        # Try relative to current directory
        $artifactsFullPath = Join-Path (Get-Location) $ArtifactsPath
    }

    # For github mode, we need to be in a git repo
    if ($DeploymentMode -eq 'github') {
        Write-Err "Not in a Git repository. The 'github' mode requires running from within a git repository."
        exit 1
    }

    Write-Warn "Not in a Git repository. Using path: $artifactsFullPath"
}

if (-not (Test-Path $artifactsFullPath)) {
    Write-Err "Artifacts path not found: $artifactsFullPath"
    Write-Err "Tip: You can specify an absolute path with -ArtifactsPath"
    exit 1
}

# Extract storage account name from URL for notebook/SQL placeholders
$storageAccountName = ""
if ($StorageAccountUrl -match 'https://([^.]+)\.') {
    $storageAccountName = $Matches[1]
}

# Extract Cosmos account name from endpoint for notebook/SQL placeholders
$cosmosAccountName = ""
if ($CosmosEndpoint -match 'https://([^.]+)\.') {
    $cosmosAccountName = $Matches[1]
}

# Define placeholder replacements
$replacements = @{
    '<REPLACE_WITH_STORAGE_BLOB_ENDPOINT>' = $StorageAccountUrl
    '<REPLACE_WITH_FUNCTION_APP_URL>'      = $FunctionAppUrl
    '<REPLACE_WITH_COSMOS_ENDPOINT>'       = $CosmosEndpoint
    '<REPLACE_WITH_KEY_VAULT_URL>'         = $KeyVaultUrl
    '<STORAGE_ACCOUNT>'                    = $storageAccountName
    '<COSMOS_ACCOUNT>'                     = $cosmosAccountName
    '<COSMOS_ACCOUNT_KEY>'                 = ''  # Not auto-populated for security - must be set manually or via linked service
}

# =============================================================================
# DIRECT DEPLOYMENT MODE
# =============================================================================

if ($DeploymentMode -eq 'direct') {
    Write-Info "Deploying artifacts directly to Synapse workspace..."

    # Deploy Linked Services first (dependencies)
    $linkedServicesPath = Join-Path $artifactsFullPath "linkedService"
    if (Test-Path $linkedServicesPath) {
        Write-Info "Deploying Linked Services..."
        $linkedServices = Get-ChildItem -Path $linkedServicesPath -Filter "*.json"

        foreach ($ls in $linkedServices) {
            Write-Info "  Deploying: $($ls.Name)"
            $content = Get-Content $ls.FullName -Raw
            $content = Replace-Placeholders -Content $content -Replacements $replacements

            # Write to temp file
            $tempFile = [System.IO.Path]::GetTempFileName() + ".json"
            $content | Out-File -FilePath $tempFile -Encoding utf8

            try {
                az synapse linked-service create `
                    --workspace-name $WorkspaceName `
                    --name ($ls.BaseName -replace '^ls_', 'LS_') `
                    --file "@$tempFile" `
                    --only-show-errors

                if ($LASTEXITCODE -eq 0) {
                    Write-Success "    Deployed: $($ls.BaseName)"
                } else {
                    Write-Warn "    Failed to deploy: $($ls.BaseName)"
                }
            }
            finally {
                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
            }
        }
    }

    # Deploy Datasets
    $datasetsPath = Join-Path $artifactsFullPath "dataset"
    if (Test-Path $datasetsPath) {
        Write-Info "Deploying Datasets..."
        $datasets = Get-ChildItem -Path $datasetsPath -Filter "*.json"

        foreach ($ds in $datasets) {
            Write-Info "  Deploying: $($ds.Name)"
            $content = Get-Content $ds.FullName -Raw
            $content = Replace-Placeholders -Content $content -Replacements $replacements

            $tempFile = [System.IO.Path]::GetTempFileName() + ".json"
            $content | Out-File -FilePath $tempFile -Encoding utf8

            try {
                az synapse dataset create `
                    --workspace-name $WorkspaceName `
                    --name ($ds.BaseName -replace '^ds_', 'DS_') `
                    --file "@$tempFile" `
                    --only-show-errors

                if ($LASTEXITCODE -eq 0) {
                    Write-Success "    Deployed: $($ds.BaseName)"
                } else {
                    Write-Warn "    Failed to deploy: $($ds.BaseName)"
                }
            }
            finally {
                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
            }
        }
    }

    # Deploy Pipelines
    $pipelinesPath = Join-Path $artifactsFullPath "pipeline"
    if (Test-Path $pipelinesPath) {
        Write-Info "Deploying Pipelines..."
        $pipelines = Get-ChildItem -Path $pipelinesPath -Filter "*.json"

        foreach ($pipeline in $pipelines) {
            Write-Info "  Deploying: $($pipeline.Name)"
            $content = Get-Content $pipeline.FullName -Raw
            $content = Replace-Placeholders -Content $content -Replacements $replacements

            $tempFile = [System.IO.Path]::GetTempFileName() + ".json"
            $content | Out-File -FilePath $tempFile -Encoding utf8

            try {
                # Extract pipeline name from JSON
                $pipelineJson = $content | ConvertFrom-Json
                $pipelineName = $pipelineJson.name

                az synapse pipeline create `
                    --workspace-name $WorkspaceName `
                    --name $pipelineName `
                    --file "@$tempFile" `
                    --only-show-errors

                if ($LASTEXITCODE -eq 0) {
                    Write-Success "    Deployed: $pipelineName"
                } else {
                    Write-Warn "    Failed to deploy: $pipelineName"
                }
            }
            finally {
                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
            }
        }
    }

    # Deploy Notebooks
    $notebooksPath = Join-Path $artifactsFullPath "notebook"
    if (Test-Path $notebooksPath) {
        Write-Info "Deploying Notebooks..."
        $notebooks = Get-ChildItem -Path $notebooksPath -Filter "*.json"

        foreach ($notebook in $notebooks) {
            Write-Info "  Deploying: $($notebook.Name)"
            $content = Get-Content $notebook.FullName -Raw
            $content = Replace-Placeholders -Content $content -Replacements $replacements

            $tempFile = [System.IO.Path]::GetTempFileName() + ".json"
            $content | Out-File -FilePath $tempFile -Encoding utf8

            try {
                # Extract notebook name from JSON
                $notebookJson = $content | ConvertFrom-Json
                $notebookName = $notebookJson.name

                az synapse notebook create `
                    --workspace-name $WorkspaceName `
                    --name $notebookName `
                    --file "@$tempFile" `
                    --only-show-errors

                if ($LASTEXITCODE -eq 0) {
                    Write-Success "    Deployed: $notebookName"
                } else {
                    Write-Warn "    Failed to deploy: $notebookName"
                }
            }
            finally {
                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
            }
        }
    }

    # Deploy SQL Scripts
    $sqlScriptsPath = Join-Path $artifactsFullPath "sqlscript"
    if (Test-Path $sqlScriptsPath) {
        Write-Info "Deploying SQL Scripts..."
        $sqlScripts = Get-ChildItem -Path $sqlScriptsPath -Filter "*.json"

        foreach ($sqlScript in $sqlScripts) {
            Write-Info "  Deploying: $($sqlScript.Name)"
            $content = Get-Content $sqlScript.FullName -Raw
            $content = Replace-Placeholders -Content $content -Replacements $replacements

            $tempFile = [System.IO.Path]::GetTempFileName() + ".json"
            $content | Out-File -FilePath $tempFile -Encoding utf8

            try {
                # Extract SQL script name from JSON
                $sqlScriptJson = $content | ConvertFrom-Json
                $sqlScriptName = $sqlScriptJson.name

                az synapse sql-script create `
                    --workspace-name $WorkspaceName `
                    --name $sqlScriptName `
                    --file "@$tempFile" `
                    --only-show-errors

                if ($LASTEXITCODE -eq 0) {
                    Write-Success "    Deployed: $sqlScriptName"
                } else {
                    Write-Warn "    Failed to deploy: $sqlScriptName"
                }
            }
            finally {
                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
            }
        }
    }

    Write-Success "Direct deployment completed!"
}

# =============================================================================
# GITHUB DEPLOYMENT MODE (This Repository)
# =============================================================================

elseif ($DeploymentMode -eq 'github') {
    Write-Info "Deploying artifacts via GitHub (this repository)..."
    Write-Info "Target branch: $GitHubBranch"

    # Check current branch
    $currentBranch = git rev-parse --abbrev-ref HEAD
    Write-Info "Current branch: $currentBranch"

    if ($currentBranch -ne $GitHubBranch) {
        Write-Warn "You are not on the target branch ($GitHubBranch)."
        Write-Warn "Please ensure you're on the correct branch or create a PR."
    }

    # Check for uncommitted changes in synapse folder
    $changedFiles = git status --porcelain $ArtifactsPath

    if (-not $changedFiles) {
        Write-Info "No changes detected in Synapse artifacts."
        exit 0
    }

    Write-Info "Changed files:"
    $changedFiles | ForEach-Object { Write-Info "  $_" }

    # Replace placeholders in all JSON files
    Write-Info "Processing artifact files with parameter substitution..."
    $jsonFiles = Get-ChildItem -Path $artifactsFullPath -Filter "*.json" -Recurse

    foreach ($jsonFile in $jsonFiles) {
        $content = Get-Content $jsonFile.FullName -Raw
        $newContent = Replace-Placeholders -Content $content -Replacements $replacements

        if ($content -ne $newContent) {
            Write-Info "  Updated: $($jsonFile.Name)"
            $newContent | Out-File -FilePath $jsonFile.FullName -Encoding utf8 -NoNewline
        }
    }

    # Stage changes
    Write-Info "Staging changes..."
    git add $ArtifactsPath

    # Commit changes
    Write-Info "Committing changes..."
    git commit -m "$CommitMessage"

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Changes committed successfully."
        Write-Info ""
        Write-Info "Next steps:"
        Write-Info "  1. Push changes: git push origin $GitHubBranch"
        Write-Info "  2. Synapse will automatically sync from the collaboration branch"
        Write-Info "  3. Publish from Synapse Studio to deploy to the live workspace"
    } else {
        Write-Warn "No changes to commit or commit failed."
    }
}

# =============================================================================
# EXTERNAL GITHUB DEPLOYMENT MODE
# =============================================================================

elseif ($DeploymentMode -eq 'external-github') {
    Write-Info "Deploying artifacts to external GitHub repository..."

    if (-not $ExternalRepoUrl) {
        Write-Err "ExternalRepoUrl is required for 'external-github' mode."
        Write-Err "Example: -ExternalRepoUrl 'https://github.com/your-org/synapse-artifacts.git'"
        exit 1
    }

    Write-Info "External repo: $ExternalRepoUrl"
    Write-Info "Target branch: $GitHubBranch"
    Write-Info "Root folder: $ExternalRepoRootFolder"

    # Create temp directory for external repo
    $tempDir = Join-Path $env:TEMP "synapse-deploy-$(Get-Date -Format 'yyyyMMddHHmmss')"
    Write-Info "Cloning external repository to: $tempDir"

    try {
        # Clone the external repository
        git clone --branch $GitHubBranch --depth 1 $ExternalRepoUrl $tempDir 2>&1
        if ($LASTEXITCODE -ne 0) {
            # Branch might not exist, try cloning without branch and create it
            Write-Warn "Branch '$GitHubBranch' not found, cloning default branch..."
            git clone --depth 1 $ExternalRepoUrl $tempDir 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Err "Failed to clone repository: $ExternalRepoUrl"
                exit 1
            }

            # Create and checkout the branch
            Push-Location $tempDir
            git checkout -b $GitHubBranch
            Pop-Location
        }

        # Determine destination path in external repo
        $externalRootFolder = $ExternalRepoRootFolder.TrimStart('/')
        $destinationPath = if ($externalRootFolder) {
            Join-Path $tempDir $externalRootFolder
        } else {
            $tempDir
        }

        Write-Info "Destination path: $destinationPath"

        # Copy artifacts with placeholder substitution
        Write-Info "Copying and processing artifacts..."
        Write-Info "Artifacts source: $artifactsFullPath"
        $filesCopied = Copy-ArtifactsWithSubstitution -SourcePath $artifactsFullPath -DestinationPath $destinationPath -Replacements $replacements

        if ($filesCopied -eq 0) {
            Write-Warn "No files were copied. Check that the source artifacts path exists and contains JSON files."
            Write-Info "Expected structure (Synapse uses singular folder names):"
            Write-Info "  $artifactsFullPath/linkedService/*.json"
            Write-Info "  $artifactsFullPath/dataset/*.json"
            Write-Info "  $artifactsFullPath/pipeline/*.json"
            Write-Info "  $artifactsFullPath/notebook/*.json"
            Write-Info "  $artifactsFullPath/sqlscript/*.json"
        }

        # Navigate to the external repo
        Push-Location $tempDir

        try {
            # Check for changes
            $changes = git status --porcelain
            if (-not $changes) {
                Write-Info "No changes to commit in external repository."
                Pop-Location
                exit 0
            }

            Write-Info "Changes detected:"
            $changes | ForEach-Object { Write-Info "  $_" }

            # Stage all changes
            Write-Info "Staging changes..."
            git add -A

            # Commit changes
            Write-Info "Committing changes..."
            $fullCommitMessage = "$CommitMessage`n`nSource: FormExtraction pipeline artifacts`nTimestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss UTC')"
            git commit -m $fullCommitMessage

            if ($LASTEXITCODE -eq 0) {
                Write-Success "Changes committed successfully."

                # Push changes
                Write-Info "Pushing changes to remote..."
                git push origin $GitHubBranch

                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Changes pushed successfully to $ExternalRepoUrl"
                    Write-Info ""
                    Write-Info "Next steps:"
                    Write-Info "  1. Synapse will automatically sync from the collaboration branch"
                    Write-Info "  2. Publish from Synapse Studio to deploy to the live workspace"
                } else {
                    Write-Err "Failed to push changes. Check your permissions."
                    exit 1
                }
            } else {
                Write-Warn "No changes to commit or commit failed."
            }
        }
        finally {
            Pop-Location
        }
    }
    finally {
        # Cleanup temp directory
        if ($CleanupTempFolder -and (Test-Path $tempDir)) {
            Write-Info "Cleaning up temporary directory..."
            Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        } elseif (Test-Path $tempDir) {
            Write-Info "Temporary directory preserved at: $tempDir"
        }
    }
}

Write-Info ""
Write-Success "Synapse artifact deployment script completed!"
