$ErrorActionPreference = 'Stop'

Write-Host "[run_local] Starting platform-api-app stack..."
docker compose up --build -d

Write-Host "[run_local] Waiting briefly for API startup..."
Start-Sleep -Seconds 5

Write-Host "[run_local] Health check: http://localhost:8000/healthz"
try {
  $health = Invoke-RestMethod -Uri "http://localhost:8000/healthz" -Method Get
  $health | ConvertTo-Json -Depth 5
} catch {
  Write-Error "Health check failed: $($_.Exception.Message)"
  exit 1
}
