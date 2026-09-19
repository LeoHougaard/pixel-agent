[CmdletBinding()]
param(
    [string]$Destination = "/sdcard/Download/pixel-agent",
    [string]$Serial
)

$ErrorActionPreference = "Stop"
$Adb = Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"
if (-not (Test-Path -LiteralPath $Adb)) {
    throw "ADB was not found at $Adb"
}

$DeviceLines = & $Adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "\tdevice$" }
if (-not $Serial -and @($DeviceLines).Count -ne 1) {
    throw "Expected exactly one connected Android device; found $(@($DeviceLines).Count). Enable Wireless debugging and pair this PC first."
}
if (-not $Serial) { $Serial = (@($DeviceLines)[0] -split '\s+')[0] }
if ((& $Adb -s $Serial get-state) -ne 'device') { throw "Device $Serial is not ready." }

$Source = $PSScriptRoot
$Files = @(
    "README.md",
    "pixel_agent.py",
    "pixel-phone-bridge.py",
    "pixel-phone-bridge-start.sh",
    "pixel-phone.sh",
    "pixel-opencode-setup.sh",
    "install-pixel-phone.sh",
    "pixel-phone-guest-setup.sh",
    "pixel-agent-key.sh",
    "install-termux.sh",
    "install-linux-desktop.sh",
    "pixel-desktop-start.sh",
    "pixel-desktop-stop.sh",
    "pixel-desktop-ui.sh",
    "apply-desktop-launcher.sh",
    "apply-desktop-usability.sh",
    "desktop-usability-repair.sh",
    "pixel-desktop-session.sh",
    "pixel-desktop-style.sh",
    "pixel-desktop-side-panel.sh",
    "pixel-wallpaper.svg",
    "pixel-t3.svg",
    "pixel-t3-browser.sh",
    "pixel-desktop-doctor.sh",
    "pixel-t3-mobile.sh",
    "pixel-t3-runtime.py",
    "pixel-app-control.py",
    "pixel-desktop-control.py",
    "pixel-checkpoint.py",
    "pixel-projects.py",
    "pixel-project-register.mjs",
    "pixel-t3-watch.mjs",
    "apply-pixel-power.sh",
    "pixel-t3-server.sh",
    "pixel-t3-desktop.sh",
    "pixel-desktop-guest-setup.sh",
    "zen-wrapper.sh",
    "orca-slicer-wrapper.sh",
    "uninstall-linux-desktop.sh"
)

& $Adb -s $Serial shell mkdir -p $Destination
foreach ($File in $Files) {
    & $Adb -s $Serial push (Join-Path $Source $File) "$Destination/$File"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy $File"
    }
}
& $Adb -s $Serial shell mkdir -p "$Destination/pixel-opencode/tools"
foreach ($File in @(
    "pixel-opencode/opencode.json",
    "pixel-opencode/AGENTS.md",
    "pixel-opencode/tools/pixel_desktop.ts",
    "pixel-opencode/tools/pixel_run.ts",
    "pixel-opencode/tools/pixel_ui.ts",
    "pixel-opencode/tools/pixel_screenshot.ts"
)) {
    & $Adb -s $Serial push (Join-Path $Source $File) "$Destination/$File"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy $File"
    }
}

Write-Host "Pixel Agent was copied to $Destination"
Write-Host "In Termux, run:"
Write-Host "  termux-setup-storage"
Write-Host "  cd ~/storage/downloads/pixel-agent && bash install-termux.sh"
