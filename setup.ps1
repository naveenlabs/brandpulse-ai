[CmdletBinding()]
param(
    [switch]$SavedReportsOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$OllamaModel = "llama3.1:8b"
$OllamaUrl = "http://127.0.0.1:11434/api/tags"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonCommand = $null

function Write-Step([string]$Message) {
    Write-Host "`n$Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$env:Path;$machine;$user"

    $wingetLinks = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
    if (Test-Path $wingetLinks) {
        $env:Path = "$wingetLinks;$env:Path"
    }
}

function Install-WingetPackage([string]$Id, [string]$Name) {
    Write-Step "Installing $Name"
    & winget install --id $Id -e --source winget --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "$Name could not be installed by Windows Package Manager."
    }
    Refresh-ProcessPath
}

function Test-Python311 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 11))" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $script:PythonCommand = "py"
            return $true
        }
    }
    if (Get-Command python3.11 -ErrorAction SilentlyContinue) {
        & python3.11 -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 11))" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $script:PythonCommand = "python3.11"
            return $true
        }
    }
    return $false
}

function Invoke-Python311([string[]]$Arguments) {
    if ($script:PythonCommand -eq "py") {
        & py -3.11 @Arguments
    }
    else {
        & python3.11 @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.11 returned an error."
    }
}

function Prepare-Python {
    Write-Step "Preparing Python 3.11"
    Set-Location $ProjectRoot
    if (Test-Path $VenvPython) {
        & $VenvPython -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 11))"
        if ($LASTEXITCODE -ne 0) {
            throw ".venv uses a different Python version. Remove .venv and rerun setup."
        }
        Write-Ok "Reusing the existing Python 3.11 environment"
    }
    else {
        if (-not (Test-Python311)) {
            Install-WingetPackage "Python.Python.3.11" "Python 3.11"
        }
        if (-not (Test-Python311)) {
            throw "Python 3.11 installed but is not available. Reopen PowerShell and rerun setup."
        }
        Invoke-Python311 -Arguments @("-m", "venv", ".venv")
        Write-Ok "Created .venv with Python 3.11"
    }

    & $VenvPython -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { throw "pip could not be prepared." }
    & $VenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "The Python packages could not be installed." }
    Write-Ok "Installed the Python packages"
}

function Find-Ollama {
    $command = Get-Command ollama -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $candidate) {
        $env:Path = "$(Split-Path $candidate);$env:Path"
        return $candidate
    }
    return $null
}

function Test-OllamaReady {
    try {
        Invoke-RestMethod -Uri $OllamaUrl -Method Get -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Prepare-AnalysisTools {
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Install-WingetPackage "Gyan.FFmpeg" "ffmpeg"
    }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        throw "ffmpeg installed but is not available. Reopen PowerShell and rerun setup."
    }
    Write-Ok "ffmpeg is installed"

    $ollama = Find-Ollama
    if (-not $ollama) {
        Install-WingetPackage "Ollama.Ollama" "Ollama"
        $ollama = Find-Ollama
    }
    if (-not $ollama) {
        throw "Ollama installed but is not available. Reopen PowerShell and rerun setup."
    }
    Write-Ok "Ollama is installed"

    if (-not (Test-OllamaReady)) {
        Write-Step "Starting Ollama"
        Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
        foreach ($attempt in 1..30) {
            if (Test-OllamaReady) { break }
            Start-Sleep -Seconds 1
        }
    }
    if (-not (Test-OllamaReady)) {
        throw "Ollama did not start. Run 'ollama serve' in another PowerShell window, then rerun setup."
    }
    Write-Ok "Ollama is running"

    Write-Step "Downloading the local controller model"
    & $ollama pull $OllamaModel
    if ($LASTEXITCODE -ne 0) { throw "$OllamaModel could not be downloaded." }
    & $ollama show $OllamaModel *> $null
    if ($LASTEXITCODE -ne 0) { throw "$OllamaModel was not found after download." }
    Write-Ok "$OllamaModel is ready"
}

function Prepare-EnvironmentFile {
    $environmentFile = Join-Path $ProjectRoot ".env"
    if (Test-Path $environmentFile) {
        Write-Ok "Kept the existing private .env file"
    }
    else {
        Copy-Item (Join-Path $ProjectRoot ".env.example") $environmentFile
        Write-Ok "Created .env from .env.example"
    }
}

try {
    Set-Location $ProjectRoot
    Write-Host "BrandPulse AI setup" -ForegroundColor White

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Windows Package Manager (winget) is required. Install 'App Installer' from Microsoft Store, then rerun setup."
    }
    if ($ProjectRoot.Length -gt 80) {
        Write-Warning "This folder has a long path. If pip reports a Windows path-length error, move the project to C:\brandpulse-ai and rerun setup."
    }

    Prepare-Python
    if (-not $SavedReportsOnly) {
        Prepare-AnalysisTools
    }
    Prepare-EnvironmentFile

    Write-Step "Setup complete"
    Write-Host "Run the application with:`n"
    Write-Host "  .\.venv\Scripts\python.exe -m flask --app app run --port 5001`n"
    Write-Host "Then open http://localhost:5001"
    if (-not $SavedReportsOnly) {
        Write-Host "Before a new analysis, open .env and replace the YouTube API key placeholder."
    }
}
catch {
    Write-Host "`nSetup stopped: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
