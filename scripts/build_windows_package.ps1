$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $RepositoryRoot
try {
    $Version = (& python -c "import platform; print(platform.python_version())").Trim()
    if ($Version -ne "3.15.0rc2") {
        throw "Windows package build requires CPython 3.15.0rc2 x64 for its bundled Tk 9 runtime; found $Version."
    }

    $Architecture = (& python -c "import platform; print(platform.machine())").Trim()
    if ($Architecture -notin @("AMD64", "x86_64")) {
        throw "Windows x64 package build requires an x64 interpreter; found $Architecture."
    }

    $TkCheck = & python -c "import tkinter; print(f'{tkinter.TkVersion:.1f}')"
    if ([double]$TkCheck.Trim() -lt 9.0) {
        throw "Tcl/Tk 9.0 or newer is required; found $($TkCheck.Trim())."
    }

    & python -m pip install --disable-pip-version-check --requirement requirements-windows-packaging.txt
    if ($LASTEXITCODE -ne 0) { throw "Installing pinned Windows packaging requirements failed." }

    & python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "The Windows packaging environment has inconsistent dependencies." }

    & python -m PyInstaller --clean --noconfirm "packaging/windows/InfoCarry-Manager.spec"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed to build the Windows Manager." }

    $OutputDirectory = Join-Path $RepositoryRoot "dist/InfoCarry Manager"
    $Executable = Join-Path $OutputDirectory "InfoCarry Manager.exe"
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "The expected packaged launcher was not produced: $Executable"
    }

    $BuildInfo = [ordered]@{
        artifact = "InfoCarry Manager.exe"
        package_layout = "onedir"
        architecture = $Architecture
        python_version = $Version
        python_implementation = (& python -c "import platform; print(platform.python_implementation())").Trim()
        tcl_tk_binding_version = (& python -c "import tkinter; print(f'{tkinter.TkVersion:.1f}')").Trim()
        pyinstaller_version = (& python -m PyInstaller --version).Trim()
        source_entry_point = "scripts/windows_manager_entry.py"
        resource_root = "_internal"
        usb_driver_installation_included = $false
    }
    $BuildInfoPath = Join-Path $OutputDirectory "BUILD-INFO.json"
    $BuildInfo | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $BuildInfoPath -Encoding utf8

    Write-Output "Windows package created: $Executable"
    Write-Output "Package directory: $OutputDirectory"
    Write-Output "Build metadata: $BuildInfoPath"
}
finally {
    Pop-Location
}
