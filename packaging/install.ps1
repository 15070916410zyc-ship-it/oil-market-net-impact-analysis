param(
    [string]$InstallRoot = ""
)

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $InstallRoot) {
    $DefaultInstallRoot = Join-Path $env:LOCALAPPDATA "MultiscaleNetImpactAnalysis"
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = "Choose where to install Multiscale Net-Impact Analysis System"
        $dialog.SelectedPath = $DefaultInstallRoot
        $dialog.ShowNewFolderButton = $true
        $dialogResult = $dialog.ShowDialog()
        if ($dialogResult -eq [System.Windows.Forms.DialogResult]::OK) {
            $InstallRoot = $dialog.SelectedPath
        }
        else {
            Write-Host "Installation cancelled."
            exit 1
        }
    }
    catch {
        Write-Host "Folder picker is unavailable. Using the default install folder."
        $InstallRoot = $DefaultInstallRoot
    }
}
$Launcher = Join-Path $InstallRoot "Start_Net_Impact_Analysis.bat"

Write-Host "Installing Multiscale Net-Impact Analysis System..."
Write-Host "Source: $SourceRoot"
Write-Host "Destination: $InstallRoot"

New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null

$robocopyArgs = @(
    $SourceRoot,
    $InstallRoot,
    "/E",
    "/XD", ".git", ".venv", "dist", "__pycache__",
    "/XF", ".env", "API.env", "install.ps1", "Install_Net_Impact_Analysis.bat",
    "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
)

& robocopy @robocopyArgs | Out-Null
$exitCode = $LASTEXITCODE
if ($exitCode -gt 7) {
    throw "File copy failed with robocopy exit code $exitCode."
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Multiscale Net-Impact Analysis.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $Launcher
$shortcut.WorkingDirectory = $InstallRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "Launch Multiscale Net-Impact Analysis System"
$shortcut.Save()

Write-Host ""
Write-Host "Installation completed."
Write-Host "Desktop shortcut: $shortcutPath"
Write-Host "Installed launcher: $Launcher"
Write-Host ""
Write-Host "Double-click the desktop shortcut to start the dashboard."
Write-Host "The first launch creates a local Python virtual environment and installs required packages."
