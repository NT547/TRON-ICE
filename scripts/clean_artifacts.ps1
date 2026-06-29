param(
    [switch] $Apply
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$targets = @(
    "result",
    "results",
    "ground-truth/output",
    "ground-truth/result",
    "ground-truth/log"
)

foreach ($relative in $targets) {
    $path = Join-Path $repo $relative
    if (-not (Test-Path -LiteralPath $path)) {
        continue
    }

    $resolved = Resolve-Path -LiteralPath $path
    if (-not $resolved.Path.StartsWith($repo.Path)) {
        throw "Refusing to clean outside repo: $($resolved.Path)"
    }

    if ($Apply) {
        Get-ChildItem -LiteralPath $resolved.Path -Force | Remove-Item -Recurse -Force
        Write-Host "Cleaned $relative"
    } else {
        Write-Host "Would clean $relative"
        Get-ChildItem -LiteralPath $resolved.Path -Recurse -File -Force |
            Select-Object -First 20 FullName, Length
    }
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry run only. Re-run with -Apply to delete generated artifacts."
}
