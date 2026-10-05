$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    Get-Content frontend/package.json -Raw | ConvertFrom-Json | Out-Null
    Get-Content frontend/tsconfig.json -Raw | ConvertFrom-Json | Out-Null
    Get-Content data/synthetic/config.json -Raw | ConvertFrom-Json | Out-Null
    $missing = @()
    Get-ChildItem backend/src,backend/tests -Filter *.py -Recurse | ForEach-Object {
        $content = [IO.File]::ReadAllText($_.FullName)
        foreach ($match in [regex]::Matches($content, '(?m)^from (stockpilot[\w.]*) import ')) {
            $path = Join-Path 'backend/src' $match.Groups[1].Value.Replace('.', '/')
            if (-not (Test-Path "$path.py") -and -not (Test-Path $path)) { $missing += $path }
        }
    }
    if ($missing.Count) { throw "Missing internal imports: $($missing -join ', ')" }
    $errors = $null; $tokens = $null
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $root 'scripts/tasks.ps1'),[ref]$tokens,[ref]$errors) | Out-Null
    if ($errors.Count) { throw "$errors" }
    Write-Output 'JSON, PowerShell syntax and internal Python module paths passed. This is not a Python/TypeScript compile or runtime test.'
} finally { Pop-Location }
