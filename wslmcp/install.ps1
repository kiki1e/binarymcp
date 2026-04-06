# PwnMCP Kiki1e - Windows Environment Setup & WSL Configuration
# This script detects the environment and configures WSL on Windows hosts.

# Set error preference
$ErrorActionPreference = "Stop"

# Color output functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check Administrator privileges
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Check if WSL is installed
function Test-WSLInstalled {
    try {
        $wslInfo = wsl --list --verbose 2>$null
        return $true
    }
    catch {
        return $false
    }
}

# Install WSL
function Install-WSL {
    Write-Info "Starting WSL installation..."
    
    if (-not (Test-Administrator)) {
        Write-ErrorMsg "Administrator privileges are required to install WSL."
        Write-Info "Please right-click PowerShell and select 'Run as Administrator'."
        exit 1
    }
    
    # Enable WSL feature
    Write-Info "Enabling Microsoft-Windows-Subsystem-Linux feature..."
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
    
    # Enable Virtual Machine Platform
    Write-Info "Enabling VirtualMachinePlatform feature..."
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
    
    Write-Success "WSL features enabled."
    Write-Warning "A computer restart is required to complete the installation."
    
    $reboot = Read-Host "Do you want to restart now? (y/N)"
    if ($reboot -eq 'y' -or $reboot -eq 'Y') {
        Restart-Computer
    }
    else {
        Write-Info "Please restart your computer manually and re-run this script."
        exit 0
    }
}

# Check for Ubuntu WSL distro and return its name
function Get-UbuntuDistroName {
    try {
        # Force output to a single string to avoid newline/encoding parsing issues
        $output = wsl --list --verbose | Out-String
        
        # Regex search for Ubuntu-like name in the entire text blob
        if ($output -match "(Ubuntu[\w\-\.]*)") {
            return $matches[1]
        }
        return $null
    }
    catch {
        return $null
    }
}

# Install Ubuntu WSL
function Install-UbuntuWSL {
    Write-Info "Starting Ubuntu WSL installation..."
    
    Write-Info "Available Ubuntu versions:"
    Write-Host "  1. Ubuntu (Latest LTS)"
    Write-Host "  2. Ubuntu-22.04"
    Write-Host "  3. Ubuntu-24.04"
    
    $choice = Read-Host "Please select a version (1-3)"
    
    $distro = switch ($choice) {
        "1" { "Ubuntu" }
        "2" { "Ubuntu-22.04" }
        "3" { "Ubuntu-24.04" }
        default { "Ubuntu" }
    }
    
    Write-Info "Installing $distro..."
    wsl --install -d $distro
    
    Write-Success "Ubuntu WSL installed successfully."
    Write-Info "Please set your Ubuntu username and password in the popup window."
}

# Set WSL 2 as default version
function Set-WSL2Default {
    Write-Info "Setting WSL 2 as the default version..."
    wsl --set-default-version 2
    Write-Success "WSL 2 is set as default."
}

# Check Docker Desktop
function Test-DockerDesktop {
    return [bool](Get-Command docker -ErrorAction SilentlyContinue)
}

# Execute install script inside WSL
function Invoke-WSLInstall {
    param(
        [string]$DistroName,
        [string]$WslPath
    )
    
    Write-Info "Preparing to install PwnMCP inside WSL..."
    Write-Info "Project WSL Path: $WslPath"
    
    # Grant execute permission to install.sh
    Write-Info "Granting execute permission to install.sh..."
    wsl -d $DistroName --cd $WslPath -- bash -c "chmod +x install.sh"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to chmod install.sh inside WSL!"
    }
    
    # Execute install script
    Write-Info "Executing installation inside WSL..."
    Write-Warning "This may take a few minutes, please wait..."
    
    wsl -d $DistroName --cd $WslPath -- bash -c "./install.sh"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to execute install.sh inside WSL!"
    }
    
    Write-Success "WSL environment configuration complete."
}

# Ensure .env file exists
function Ensure-EnvFile {
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Write-Info ".env config not found, creating from .env.example..."
            Copy-Item ".env.example" ".env"
            Write-Success ".env file created."
        } else {
            Write-Warning ".env.example template not found, cannot auto-create config file."
        }
    } else {
        Write-Info ".env file already exists."
    }
}

# Show usage
function Show-Usage {
    param([string]$WslPath)
    Write-Host ""
    Write-Host "=========================================="
    Write-Success "Configuration Complete!"
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "🚀 How to use:"
    Write-Host ""
    Write-Host "Method 1: Run inside WSL (Recommended)"
    Write-Host "  1. Open WSL terminal:"
    Write-Host "     wsl"
    Write-Host ""
    Write-Host "  2. Go to project directory:"
    Write-Host "     cd \"$WslPath\""
    Write-Host ""
    Write-Host "  3. Start the server:"
    Write-Host "     ./start.sh"
    Write-Host ""
    Write-Host "Method 2: Use Docker Desktop"
    Write-Host "  1. Start Docker Desktop"
    Write-Host "  2. Open PowerShell in project dir:"
    Write-Host "     docker build -t pwnmcp-kiki1e ."
    Write-Host "     docker run -it --rm pwnmcp-kiki1e"
    Write-Host ""
    Write-Host "📚 See README.md for more info."
    Write-Host ""
}

# Main function
function Main {
    Write-Host "=========================================="
    Write-Host "  PwnMCP Kiki1e - Windows Setup Wizard"
    Write-Host "=========================================="
    Write-Host ""
    
    # 0. Ensure config file exists
    Ensure-EnvFile
    
    # 1. Check WSL
    if (-not (Test-WSLInstalled)) {
        Write-Warning "WSL not detected."
        $install = Read-Host "Install WSL now? (y/N)"
        if ($install -eq 'y' -or $install -eq 'Y') {
            Install-WSL
        }
        else {
            Write-ErrorMsg "PwnMCP requires WSL to run."
            exit 1
        }
    }
    else {
        Write-Success "WSL is installed."
    }
    
    # 2. Set WSL 2
    Set-WSL2Default
    
    # 3. Check Ubuntu and get name
    $distroName = Get-UbuntuDistroName
    
    if (-not $distroName) {
        Write-Warning "Ubuntu WSL distribution not found."
        $install = Read-Host "Install Ubuntu now? (y/N)"
        if ($install -eq 'y' -or $install -eq 'Y') {
            Install-UbuntuWSL
            # Re-check after install
            $distroName = Get-UbuntuDistroName
            if (-not $distroName) {
                 # Fallback check
                 $distroName = (wsl --list --quiet | Where-Object { $_ -match "Ubuntu" } | Select-Object -First 1)
                 if ($distroName) { $distroName = $distroName.Trim() }
            }
        }
        else {
            Write-ErrorMsg "PwnMCP requires an Ubuntu WSL distribution."
            exit 1
        }
    }
    
    if ($distroName) {
        Write-Success "Detected Ubuntu distribution: $distroName"
        
        # Check if it is the default distro
        $isDefault = (wsl --list --verbose | Select-String "\* $distroName")
        if (-not $isDefault) {
            Write-Warning "Ubuntu ($distroName) is not the default WSL distribution."
            Write-Info "Setting it as default..."
            wsl --set-default $distroName
            Write-Success "Set $distroName as default."
        }
    } else {
        Write-ErrorMsg "Could not determine Ubuntu distribution name."
    }
    
    # 4. Check Docker Desktop (Optional)
    if (Test-DockerDesktop) {
        Write-Success "Docker Desktop is installed."
        Write-Info "You can choose to run PwnMCP via Docker or WSL."
    }
    
    # Get project path
    $projectPath = (Get-Location).Path
    $driveLetter = $projectPath.Substring(0, 1).ToLower()
    $pathWithoutDrive = $projectPath.Substring(2)
    $wslPath = "/mnt/$driveLetter" + ($pathWithoutDrive -replace "\\", "/")

    # 5. Ask to install in WSL
    Write-Host ""
    $installWSL = Read-Host "Install PwnMCP dependencies inside WSL now? (y/N)"
    if ($installWSL -eq 'y' -or $installWSL -eq 'Y') {
        try {
            if (-not $distroName) {
                 $distroName = Read-Host "Cannot auto-detect. Please enter your Ubuntu distro name (e.g. 'Ubuntu-22.04')"
            }
            if ($distroName) {
                Invoke-WSLInstall -DistroName $distroName -WslPath $wslPath
            }
        }
        catch {
            Write-ErrorMsg "Error during WSL installation: $($PSItem.ToString())"
            Write-Info "You can manually run ./install.sh inside WSL."
        }
    }
    
    # Show usage
    Show-Usage -WslPath $wslPath
}

# Error trap
trap {
    Write-ErrorMsg "An error occurred: $($PSItem.ToString())"
    exit 1
}

# Run Main
Main