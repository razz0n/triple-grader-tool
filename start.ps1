# start.ps1 - Launch the Ontology Triple Grader (backend + frontend)
# Run from the workspace root: .\start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv_uvicorn = "$root\.venv\Scripts\uvicorn.exe"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Ontology Triple Grader - Startup" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# --- Backend ---
Write-Host ""
Write-Host "[1/2] Starting FastAPI backend on http://localhost:8001 ..." -ForegroundColor Yellow
Start-Process -NoNewWindow powershell -ArgumentList @(
    "-NoProfile", "-Command",
    "cd '$root\backend'; & '$venv_uvicorn' main:app --reload --port 8001"
)

Start-Sleep -Seconds 2

# --- Frontend ---
Write-Host "[2/2] Starting React frontend ..." -ForegroundColor Yellow
Start-Process -NoNewWindow powershell -ArgumentList @(
    "-NoProfile", "-Command",
    "cd '$root\frontend'; npm run dev"
)

Write-Host ""
Write-Host "--------------------------------------------------" -ForegroundColor Green
Write-Host "  Backend:   http://localhost:8001" -ForegroundColor Green
Write-Host "  API docs:  http://localhost:8001/docs" -ForegroundColor Green
Write-Host "  Frontend:  http://localhost:5173  (or 5174)" -ForegroundColor Green
Write-Host "--------------------------------------------------" -ForegroundColor Green
Write-Host ""
Write-Host "Press CTRL+C to stop." -ForegroundColor Gray

