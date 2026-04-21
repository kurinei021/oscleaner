param(
    [ValidateSet("audit", "clean", "analyze", "doctor", "status")]
    [string]$Command = "audit",
    [switch]$ConfirmCleanup,
    [switch]$Apply,
    [switch]$IncludeSystemTemp,
    [switch]$IncludePackageCache,
    [string]$JsonOut,
    [string]$LogFile
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
$ArgsList = @("$RootDir/oscleaner.py", $Command)

if ($ConfirmCleanup) { $ArgsList += "--confirm" }
if ($Apply) { $ArgsList += "--apply" }
if ($IncludeSystemTemp) { $ArgsList += "--include-system-temp" }
if ($IncludePackageCache) { $ArgsList += "--include-package-cache" }
if ($JsonOut) { $ArgsList += @("--json-out", $JsonOut) }
if ($LogFile) { $ArgsList += @("--log-file", $LogFile) }

Write-Host "Running oscleaner $Command..."
python $ArgsList
