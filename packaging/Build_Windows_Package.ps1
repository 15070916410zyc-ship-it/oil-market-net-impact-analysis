$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DistRoot = Join-Path $ProjectRoot "dist"
$StageRoot = Join-Path $DistRoot "MultiscaleNetImpactAnalysis"
$ZipPath = Join-Path $DistRoot "Multiscale_Net_Impact_Analysis_Setup.zip"
$InstallerBaseName = "Multiscale_Net_Impact_Analysis_Setup"

Write-Host "Building Windows package from $ProjectRoot"

if (Test-Path $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null
New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null

$copyItems = @(
    "app",
    "src",
    "config",
    ".streamlit",
    "requirements.txt",
    "README.md",
    "HOW_TO_SHARE.md",
    "Start_Website.bat",
    "Start_Net_Impact_Analysis.bat"
)

foreach ($item in $copyItems) {
    $source = Join-Path $ProjectRoot $item
    if (-not (Test-Path $source)) {
        throw "Required package item not found: $item"
    }
    $destination = Join-Path $StageRoot $item
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

$runtimeDirs = @(
    "data",
    "data\raw",
    "data\raw\uploads",
    "data\raw\uploads\originals",
    "data\raw\variable_pool",
    "data\processed",
    "outputs",
    "outputs\figures",
    "outputs\tables",
    "outputs\models",
    "outputs\reports"
)

foreach ($dir in $runtimeDirs) {
    New-Item -ItemType Directory -Path (Join-Path $StageRoot $dir) -Force | Out-Null
}

Get-ChildItem -LiteralPath $StageRoot -Directory -Filter "__pycache__" -Recurse -Force |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $StageRoot -File -Recurse -Force |
    Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
    Remove-Item -Force

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "Install_Net_Impact_Analysis.bat") -Destination (Join-Path $StageRoot "Install_Net_Impact_Analysis.bat") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "install.ps1") -Destination (Join-Path $StageRoot "install.ps1") -Force

@"
# Optional API keys for more stable online data refreshes.
# Rename this file to API.env and replace the values below, or use the app menu.
# FRED_API_KEY: Federal Reserve Economic Data, https://fred.stlouisfed.org/docs/api/api_key.html
# EIA_API_KEY: U.S. Energy Information Administration Open Data, https://www.eia.gov/opendata/register.php
# GPRD does not need an API key; it downloads from the official Caldara-Iacoviello daily GPR file.
FRED_API_KEY=your_key_here
EIA_API_KEY=your_key_here
"@ | Set-Content -Path (Join-Path $StageRoot "API.env.example") -Encoding UTF8

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $StageRoot "*") -DestinationPath $ZipPath -Force
Write-Host "Created portable setup zip: $ZipPath"

$isccCandidates = @(@(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LocalAppData}\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) })

if ($isccCandidates.Count -gt 0) {
    $iscc = $isccCandidates[0]
    $issPath = Join-Path $DistRoot "NetImpactAnalysis.generated.iss"
    $escapedStageRoot = $StageRoot.Replace("\", "\\")
    $escapedDistRoot = $DistRoot.Replace("\", "\\")
    @"
[Setup]
AppId={{F0D01F7B-03D3-4EA5-A3F7-9C5CB26E544F}
AppName=Multiscale Net-Impact Analysis System
AppVersion=1.0.0
AppPublisher=Net-Impact Analysis
DefaultDirName={localappdata}\MultiscaleNetImpactAnalysis
DefaultGroupName=Multiscale Net-Impact Analysis System
DisableDirPage=no
DisableProgramGroupPage=yes
UsePreviousAppDir=no
AlwaysShowDirOnReadyPage=yes
OutputDir=$escapedDistRoot
OutputBaseFilename=$InstallerBaseName
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "$escapedStageRoot\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Multiscale Net-Impact Analysis"; Filename: "{app}\Start_Net_Impact_Analysis.bat"; WorkingDir: "{app}"
Name: "{group}\Multiscale Net-Impact Analysis"; Filename: "{app}\Start_Net_Impact_Analysis.bat"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Start_Net_Impact_Analysis.bat"; Description: "Launch Multiscale Net-Impact Analysis"; Flags: postinstall skipifsilent nowait
"@ | Set-Content -Path $issPath -Encoding UTF8

    Write-Host "Inno Setup found: $iscc"
    & $iscc $issPath
    Write-Host "Created Windows installer: $(Join-Path $DistRoot "$InstallerBaseName.exe")"
}
else {
    Write-Host "Inno Setup was not found, so the .exe installer was not built."
    Write-Host "Install Inno Setup 6 and re-run this script to create an .exe installer."
}
