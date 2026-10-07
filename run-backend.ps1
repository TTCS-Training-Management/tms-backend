$backend = $PSScriptRoot
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend Python environment not found: $python"
}

Set-Location -LiteralPath $backend
& $python -m uvicorn main:app --reload
