$backend = $PSScriptRoot
$frontend = Join-Path (Split-Path -Parent $backend) "tms-frontend"

if (-not (Test-Path -LiteralPath (Join-Path $frontend "run-frontend.ps1"))) {
    throw "Frontend launcher not found under: $frontend"
}

Start-Process -FilePath "powershell.exe" `
    -WorkingDirectory $backend `
    -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", ".\run-backend.ps1")

Start-Process -FilePath "powershell.exe" `
    -WorkingDirectory $frontend `
    -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", ".\run-frontend.ps1")
