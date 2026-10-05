param([Parameter(Mandatory=$true)][ValidateSet('setup','up','migrate','seed-demo','demo','test','test-integration','lint','typecheck','e2e','fetch-retail','train-retail')][string]$Task)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$portableNode = Join-Path $root '.tools/node-v22.22.0-win-x64'
if (-not (Get-Command node -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $portableNode 'node.exe'))) {
    $env:PATH = $portableNode + ';' + $env:PATH
}
function Run-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}
Push-Location $root
try {
    switch ($Task) {
        'setup' {
            Push-Location backend
            try { Run-Checked uv @('lock'); Run-Checked uv @('sync') } finally { Pop-Location }
            Push-Location frontend
            try { Run-Checked npm.cmd @('install') } finally { Pop-Location }
        }
        'up' { Run-Checked docker @('compose','up','--build','-d') }
        'migrate' { Run-Checked docker @('compose','run','--rm','migrate') }
        'seed-demo' { Run-Checked docker @('compose','exec','api','python','-m','stockpilot.cli','seed-demo') }
        'demo' {
            Run-Checked docker @('compose','up','--build','-d')
            Run-Checked docker @('compose','exec','api','python','-m','stockpilot.cli','demo')
        }
        'fetch-retail' { Run-Checked docker @('compose','exec','api','python','-m','stockpilot.cli','fetch-retail') }
        'train-retail' { Run-Checked docker @('compose','exec','api','python','-m','stockpilot.cli','train-retail') }
        'test' {
            Push-Location backend
            try { Run-Checked uv @('run','pytest') } finally { Pop-Location }
            Push-Location frontend
            try { Run-Checked npm.cmd @('test') } finally { Pop-Location }
        }
        'test-integration' {
            Run-Checked docker @('compose','-f','compose.test.yaml','up','-d','--wait')
            $previousDatabase = $env:DATABASE_URL
            $previousTestDatabase = $env:TEST_DATABASE_URL
            $env:DATABASE_URL = 'postgresql+psycopg://stockpilot:stockpilot@127.0.0.1:5433/stockpilot_test?connect_timeout=5'
            $env:TEST_DATABASE_URL = $env:DATABASE_URL
            Push-Location backend
            try {
                Run-Checked uv @('run','--locked','alembic','upgrade','head')
                Run-Checked uv @('run','--locked','pytest','tests/integration')
            } finally {
                Pop-Location
                $env:DATABASE_URL = $previousDatabase
                $env:TEST_DATABASE_URL = $previousTestDatabase
            }
        }
        'lint' {
            Push-Location backend
            try { Run-Checked uv @('run','ruff','check','src','tests','migrations') } finally { Pop-Location }
            Push-Location frontend
            try { Run-Checked npm.cmd @('run','lint') } finally { Pop-Location }
        }
        'typecheck' {
            Push-Location backend
            try { Run-Checked uv @('run','mypy','src') } finally { Pop-Location }
            Push-Location frontend
            try { Run-Checked npm.cmd @('run','typecheck') } finally { Pop-Location }
        }
        'e2e' {
            Push-Location frontend
            try { Run-Checked npx.cmd @('playwright','install','chromium'); Run-Checked npm.cmd @('run','e2e') } finally { Pop-Location }
        }
    }
} finally { Pop-Location }
