# Complete Polyglot & Jupyter Notebooks Setup Guide

A comprehensive guide to setting up VS Code / VS Code Insiders for working with Jupyter Notebooks and Polyglot Notebooks with full Python, R, .NET, PowerShell, SQL, and KQL support.

---

## Table of Contents

1. [Prerequisites Overview](#prerequisites-overview)
2. [Install Core Software](#install-core-software)
3. [VS Code Extensions](#vs-code-extensions)
4. [Python Setup](#python-setup)
5. [R Setup](#r-setup)
6. [.NET Setup](#net-setup)
7. [Verify Kernel Installation](#verify-kernel-installation)
8. [VS Code Configuration](#vs-code-configuration)
9. [Using Jupyter Notebooks](#using-jupyter-notebooks)
10. [Using Polyglot Notebooks](#using-polyglot-notebooks)
11. [Sharing Variables Between Languages](#sharing-variables-between-languages)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites Overview

| Component | Purpose | Required For |
|-----------|---------|--------------|
| VS Code / VS Code Insiders | IDE | Everything |
| .NET 8+ SDK | Polyglot Notebooks engine | Polyglot Notebooks |
| Python 3.10+ | Python kernel | Python cells |
| Jupyter | Notebook infrastructure | Python/R kernels |
| R 4.0+ | R kernel | R cells |
| Node.js | JavaScript kernel | JavaScript cells (optional) |

---

## Install Core Software

### 1. VS Code or VS Code Insiders

**VS Code (Stable):**
- Download: https://code.visualstudio.com/
- Or via winget:
```powershell
winget install Microsoft.VisualStudioCode
```

**VS Code Insiders (Preview):**
- Download: https://code.visualstudio.com/insiders/
- Or via winget:
```powershell
winget install Microsoft.VisualStudioCode.Insiders
```

---

### 2. .NET SDK (Required for Polyglot Notebooks)

Download .NET 8 SDK (or later): https://dotnet.microsoft.com/download

Or via winget:
```powershell
winget install Microsoft.DotNet.SDK.8
```

**Verify installation:**
```powershell
dotnet --version
# Should show 8.0.x or higher
```

---

### 3. Python

#### Option A: Standalone Python (Recommended for simplicity)

Download Python 3.10+: https://www.python.org/downloads/

**Important during installation:**
- ✅ Check "Add Python to PATH"
- ✅ Check "Install pip"

Or via winget:
```powershell
winget install Python.Python.3.12
```

#### Option B: Anaconda/Miniconda (Recommended for data science)

- **Anaconda** (full): https://www.anaconda.com/download
- **Miniconda** (minimal): https://docs.conda.io/en/latest/miniconda.html

Or via winget:
```powershell
# Miniconda
winget install Anaconda.Miniconda3

# Or full Anaconda
winget install Anaconda.Anaconda3
```

**Verify installation:**
```powershell
python --version
# Should show Python 3.10.x or higher

pip --version
# Should show pip with Python path
```

---

### 4. R (Optional - for R kernel support)

Download R 4.0+: https://cran.r-project.org/

- Windows: https://cran.r-project.org/bin/windows/base/
- Choose "base" download

Or via winget:
```powershell
winget install RProject.R
```

**Verify installation:**
```powershell
R --version
# Should show R version 4.x.x
```

---

### 5. Node.js (Optional - for JavaScript enhancements)

Download: https://nodejs.org/

Or via winget:
```powershell
winget install OpenJS.NodeJS.LTS
```

---

## VS Code Extensions

### Required Extensions

Open VS Code and install these extensions:

#### 1. Jupyter Extension (for Jupyter Notebooks)
```
Name: Jupyter
ID: ms-toolsai.jupyter
```
Install via command palette: `ext install ms-toolsai.jupyter`

#### 2. Polyglot Notebooks (for multi-language notebooks)
```
Name: Polyglot Notebooks
ID: ms-dotnettools.dotnet-interactive-vscode
```
Install via command palette: `ext install ms-dotnettools.dotnet-interactive-vscode`

#### 3. Python Extension
```
Name: Python
ID: ms-python.python
```
Install via command palette: `ext install ms-python.python`

### Recommended Extensions

#### 4. R Extension (for R support)
```
Name: R
ID: REditorSupport.r
```
Install via command palette: `ext install REditorSupport.r`

#### 5. Pylance (Python IntelliSense)
```
Name: Pylance
ID: ms-python.vscode-pylance
```

#### 6. Data Wrangler (for data exploration)
```
Name: Data Wrangler
ID: ms-toolsai.datawrangler
```

### Install All at Once (Command Line)

```powershell
# For VS Code
code --install-extension ms-toolsai.jupyter
code --install-extension ms-dotnettools.dotnet-interactive-vscode
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension REditorSupport.r
code --install-extension ms-toolsai.datawrangler

# For VS Code Insiders (use 'code-insiders' instead of 'code')
code-insiders --install-extension ms-toolsai.jupyter
code-insiders --install-extension ms-dotnettools.dotnet-interactive-vscode
code-insiders --install-extension ms-python.python
code-insiders --install-extension ms-python.vscode-pylance
code-insiders --install-extension REditorSupport.r
code-insiders --install-extension ms-toolsai.datawrangler
```

---

## Python Setup

### Step 1: Install Jupyter and ipykernel

#### Using pip:
```powershell
# Install Jupyter and kernel
pip install jupyter ipykernel notebook

# Verify installation
jupyter --version
```

#### Using conda:
```powershell
conda install jupyter ipykernel notebook
```

### Step 2: Register Python Kernel

```powershell
# Register the default Python kernel
python -m ipykernel install --user --name python3 --display-name "Python 3"
```

### Step 3: Create Additional Python Environments (Optional)

#### Using venv:
```powershell
# Create virtual environment
python -m venv C:\envs\datascience

# Activate it
C:\envs\datascience\Scripts\activate

# Install packages
pip install jupyter ipykernel pandas numpy matplotlib scikit-learn

# Register as a kernel
python -m ipykernel install --user --name datascience --display-name "Data Science (Python)"

# Deactivate
deactivate
```

#### Using conda:
```powershell
# Create conda environment
conda create -n datascience python=3.11 pandas numpy matplotlib scikit-learn ipykernel

# Activate it
conda activate datascience

# Register as a kernel
python -m ipykernel install --user --name datascience --display-name "Data Science (Conda)"

# Deactivate
conda deactivate
```

### Step 4: Install Common Data Science Packages (Optional)

```powershell
pip install pandas numpy matplotlib seaborn scikit-learn plotly scipy jupyterlab
```

---

## R Setup

### Step 1: Install R (if not already done)

Download from https://cran.r-project.org/bin/windows/base/

### Step 2: Install IRkernel Package

Open **R console** (search "R" in Start menu) or **RStudio** and run:

```r
# Install IRkernel package
install.packages('IRkernel')
```

If prompted to select a CRAN mirror, choose one close to your location.

### Step 3: Register R Kernel with Jupyter

Still in R console:
```r
# Register the kernel (for current user)
IRkernel::installspec(user = TRUE)
```

If you want it available system-wide (requires admin):
```r
IRkernel::installspec(user = FALSE)
```

### Step 4: Install Common R Packages (Optional)

```r
# Data manipulation and visualization
install.packages(c('tidyverse', 'ggplot2', 'dplyr', 'tidyr'))

# Data tables
install.packages('data.table')

# Statistical modeling
install.packages(c('caret', 'randomForest', 'xgboost'))

# Interactive visualizations
install.packages('plotly')
```

### Step 5: Restart VS Code

**Important:** After installing IRkernel, restart VS Code completely for it to detect the new kernel.

---

## .NET Setup

### Step 1: Verify .NET SDK

```powershell
dotnet --list-sdks
```

You should see .NET 8.0 or higher.

### Step 2: Install .NET Interactive (Usually automatic)

The Polyglot Notebooks extension installs this automatically, but you can install manually:

```powershell
dotnet tool install -g Microsoft.dotnet-interactive
```

### Step 3: Install .NET Interactive Kernels (Optional)

```powershell
# Verify installation
dotnet interactive --version
```

---

## Verify Kernel Installation

### List All Installed Kernels

```powershell
jupyter kernelspec list
```

**Expected output:**
```
Available kernels:
  python3       C:\Users\YourName\AppData\Roaming\jupyter\kernels\python3
  datascience   C:\Users\YourName\AppData\Roaming\jupyter\kernels\datascience
  ir            C:\Users\YourName\AppData\Roaming\jupyter\kernels\ir
  .net-csharp   (managed by Polyglot extension)
  .net-fsharp   (managed by Polyglot extension)
  .net-pwsh     (managed by Polyglot extension)
```

### Test Jupyter Server

```powershell
# Start Jupyter to verify it works
jupyter notebook --no-browser

# Press Ctrl+C to stop
```

---

## VS Code Configuration

### Recommended Settings

Open VS Code Settings (Ctrl+,) or edit `settings.json`:

```json
{
    // Python settings
    "python.defaultInterpreterPath": "python",
    "python.terminal.activateEnvironment": true,

    // Jupyter settings
    "jupyter.askForKernelRestart": false,
    "jupyter.interactiveWindow.creationMode": "perFile",
    "jupyter.widgetScriptSources": ["jsdelivr.com", "unpkg.com"],
    "notebook.cellToolbarLocation": {
        "default": "right",
        "jupyter-notebook": "left"
    },

    // Polyglot Notebooks settings
    "dotnet-interactive.minimumInteractiveToolVersion": "1.0.0",
    "polyglot-notebook.kernelTransportArgs": [
        "{dotnet_path}",
        "tool",
        "run",
        "dotnet-interactive",
        "--",
        "stdio",
        "--working-dir",
        "{working_dir}"
    ],

    // R settings (if using R extension)
    "r.bracketedPaste": true,
    "r.rterm.windows": "C:\\Program Files\\R\\R-4.3.2\\bin\\R.exe",

    // Notebook settings
    "notebook.output.textLineLimit": 500,
    "notebook.formatOnSave.enabled": true,
    "notebook.codeActionsOnSave": {
        "source.fixAll": true
    },

    // File associations
    "files.associations": {
        "*.ipynb": "jupyter-notebook"
    }
}
```

### Configure Default Kernel per Workspace

Create `.vscode/settings.json` in your project:

```json
{
    "jupyter.notebookFileRoot": "${workspaceFolder}",
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe"
}
```

---

## Using Jupyter Notebooks

### Create a New Jupyter Notebook

1. **Command Palette** (Ctrl+Shift+P) → "Create: New Jupyter Notebook"
2. Or create a file with `.ipynb` extension

### Select Kernel

1. Click kernel selector in top-right corner
2. Choose "Python Environments" → Select your Python
3. Or choose "Jupyter Kernel" → Select `ir` for R

### Run Cells

- **Run cell:** Shift+Enter or click ▶️
- **Run all:** Click "Run All" in toolbar
- **Add cell:** Click + button or press B (below) / A (above)

### Example Python Cell

```python
import pandas as pd
import matplotlib.pyplot as plt

# Create sample data
df = pd.DataFrame({
    'x': range(10),
    'y': [i**2 for i in range(10)]
})

# Plot
plt.figure(figsize=(8, 5))
plt.plot(df['x'], df['y'], marker='o')
plt.title('Sample Plot')
plt.xlabel('X')
plt.ylabel('Y')
plt.show()
```

### Example R Cell

```r
# Load library
library(ggplot2)

# Create sample data
df <- data.frame(
    x = 1:10,
    y = (1:10)^2
)

# Plot
ggplot(df, aes(x = x, y = y)) +
    geom_line() +
    geom_point() +
    ggtitle("Sample R Plot") +
    theme_minimal()
```

---

## Using Polyglot Notebooks

### Create a New Polyglot Notebook

1. **Command Palette** (Ctrl+Shift+P) → "Polyglot Notebook: Create new blank notebook"
2. Select `.ipynb` format
3. Choose starting language (C#, F#, PowerShell, etc.)

### Change Cell Language

Click the language indicator in the bottom-right of each cell to switch languages.

### Available Languages (Built-in)

- C# (`#!csharp`)
- F# (`#!fsharp`)
- PowerShell (`#!pwsh`)
- JavaScript (`#!javascript`)
- HTML (`#!html`)
- Mermaid (`#!mermaid`)
- SQL (`#!sql`)
- KQL (`#!kql`)

### Connect Python Kernel

Add this cell and run it:
```
#!connect jupyter --kernel-name pythonkernel --kernel-spec python3
```

For a specific conda environment:
```
#!connect jupyter --kernel-name pythonkernel --conda-env datascience --kernel-spec python3
```

### Connect R Kernel

```
#!connect jupyter --kernel-name Rkernel --kernel-spec ir
```

### Using Connected Kernels

After connecting, use the kernel name as a magic command:

```python
#!pythonkernel
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3]})
print(df)
```

```r
#!Rkernel
library(ggplot2)
print("R is working!")
```

---

## Sharing Variables Between Languages

Polyglot Notebooks can share variables between different language kernels.

### Share from C# to Python

```csharp
#!csharp
var numbers = new[] { 1, 2, 3, 4, 5 };
var message = "Hello from C#";
```

```python
#!pythonkernel
#!set --value @csharp:numbers --name nums
#!set --value @csharp:message --name msg

print(f"Message: {msg}")
print(f"Numbers: {nums}")
```

### Share from Python to C#

```python
#!pythonkernel
result = {"status": "success", "count": 42}
```

```csharp
#!csharp
#!set --value @pythonkernel:result --name pyResult
Console.WriteLine($"Python result: {pyResult}");
```

### Share from PowerShell to Python

```powershell
#!pwsh
$data = @{
    Name = "Azure"
    Region = "eastus"
    Count = 10
}
```

```python
#!pythonkernel
#!set --value @pwsh:data --name ps_data
print(f"PowerShell data: {ps_data}")
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. "Kernel not found" or "No kernel available"

**Solution:**
```powershell
# Reinstall ipykernel
pip install --upgrade ipykernel

# Re-register kernel
python -m ipykernel install --user --name python3

# Restart VS Code
```

#### 2. "Cannot connect to Jupyter server"

**Solution:**
```powershell
# Check Jupyter installation
jupyter --version

# Reinstall Jupyter
pip install --upgrade jupyter notebook

# Clear Jupyter config
jupyter --config-dir
# Delete or rename the jupyter folder in that directory
```

#### 3. Python extension not detecting environments

**Solution:**
1. Open Command Palette (Ctrl+Shift+P)
2. Run "Python: Clear Cache and Reload Window"
3. Run "Python: Select Interpreter"

#### 4. R kernel not showing

**Solution:**
```r
# In R console, reinstall IRkernel
remove.packages('IRkernel')
install.packages('IRkernel')
IRkernel::installspec(user = TRUE)
```
Then restart VS Code.

#### 5. Polyglot Notebooks: ".NET Interactive not found"

**Solution:**
```powershell
# Install .NET Interactive globally
dotnet tool install -g Microsoft.dotnet-interactive

# Or update it
dotnet tool update -g Microsoft.dotnet-interactive

# Verify
dotnet interactive --version
```

#### 6. "The kernel died" or notebook crashes

**Solution:**
- Check for memory-intensive operations
- Update all packages: `pip install --upgrade jupyter ipykernel`
- Check VS Code Developer Tools (Help → Toggle Developer Tools) for errors

#### 7. Extensions not working in VS Code Insiders

**Solution:**
Extensions installed in VS Code don't carry over to Insiders. Install them separately:
```powershell
code-insiders --install-extension ms-toolsai.jupyter
code-insiders --install-extension ms-dotnettools.dotnet-interactive-vscode
```

#### 8. Permission errors during kernel installation

**Solution:**
```powershell
# Use --user flag
python -m ipykernel install --user --name python3

# Or run as administrator (Windows)
# Right-click PowerShell → Run as Administrator
```

#### 9. Kernel takes too long to start

**Solution:**
Add to VS Code settings:
```json
{
    "jupyter.jupyterServerType": "local",
    "jupyter.disableJupyterAutoStart": false
}
```

#### 10. Cannot import installed packages

**Solution:**
Ensure the kernel is using the correct Python environment:
```python
import sys
print(sys.executable)  # Shows which Python is being used
print(sys.path)        # Shows package search paths
```

### Reset Everything (Nuclear Option)

If all else fails:

```powershell
# Remove all Jupyter kernels
jupyter kernelspec list
jupyter kernelspec remove <kernel-name>

# Reinstall Jupyter
pip uninstall jupyter notebook ipykernel
pip install jupyter notebook ipykernel

# Re-register Python kernel
python -m ipykernel install --user --name python3

# Restart VS Code
```

---

## Quick Reference Commands

```powershell
# List kernels
jupyter kernelspec list

# Remove a kernel
jupyter kernelspec remove <kernel-name>

# Check Python location
where python
python -c "import sys; print(sys.executable)"

# Check R location
where R
R --version

# Check .NET version
dotnet --version
dotnet --list-sdks

# Install Python kernel
python -m ipykernel install --user --name <name> --display-name "<Display Name>"

# Install R kernel (in R console)
# install.packages('IRkernel')
# IRkernel::installspec(user = TRUE)

# Start Jupyter manually
jupyter notebook
jupyter lab

# VS Code extension management
code --list-extensions
code --install-extension <extension-id>
code --uninstall-extension <extension-id>
```

---

## Additional Resources

- [VS Code Jupyter Documentation](https://code.visualstudio.com/docs/datascience/jupyter-notebooks)
- [Polyglot Notebooks Documentation](https://code.visualstudio.com/docs/languages/polyglot)
- [.NET Interactive GitHub](https://github.com/dotnet/interactive)
- [Jupyter in Polyglot Notebooks](https://github.com/dotnet/interactive/blob/main/docs/jupyter-in-polyglot-notebooks.md)
- [IRkernel Documentation](https://irkernel.github.io/)
- [ipykernel Documentation](https://ipython.readthedocs.io/en/stable/install/kernel_install.html)

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2024-12 | 1.0 | Initial guide |
