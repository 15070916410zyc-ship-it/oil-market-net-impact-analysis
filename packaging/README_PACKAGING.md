# Windows Packaging

Run this from PowerShell in the project root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\Build_Windows_Package.ps1
```

The build creates:

```text
dist\Multiscale_Net_Impact_Analysis_Setup.zip
```

If Inno Setup 6 is installed, the build also creates:

```text
dist\Multiscale_Net_Impact_Analysis_Setup.exe
```

The `.exe` installer keeps the destination-folder page enabled. The zip package
installer also prompts for an installation folder.

The package intentionally excludes local secrets, virtual environments, uploaded
files, raw downloaded data, and generated analysis outputs. End users can start
with a clean installation, add their own `API.env`, and upload their own local
variables.
