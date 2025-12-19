param(
  [int]$FrontendPort = 5173,
  [int]$BackendPort = 8010,
  [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'

function Wait-HttpOk {
  param(
    [string]$Url,
    [int]$TimeoutSeconds = 60
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $lastErr = $null

  while ((Get-Date) -lt $deadline) {
    try {
      $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400) {
        return $true
      }
    } catch {
      $lastErr = $_
      Start-Sleep -Seconds 2
    }
  }

  throw "HTTP check timeout: $Url; last error: $lastErr"
}

Write-Host '[1/3] Checking docker compose status...'
try {
  docker compose ps | Out-Host
} catch {
  throw "docker compose not available or failed. Please ensure Docker Desktop is installed: $($_)"
}

Write-Host '[2/3] Checking backend /health ...'
Wait-HttpOk -Url "http://localhost:$BackendPort/health" -TimeoutSeconds $TimeoutSeconds | Out-Null
Write-Host "OK: http://localhost:$BackendPort/health"

Write-Host '[3/3] Checking frontend / and proxy /api/health ...'
Wait-HttpOk -Url "http://localhost:$FrontendPort/" -TimeoutSeconds $TimeoutSeconds | Out-Null
Write-Host "OK: http://localhost:$FrontendPort/"

# Notes:
# - Nginx proxies /api/* -> backend:8010/api/*
# - /health is proxied to backend /health
Write-Host '[3/3] Checking frontend proxy /health ...'
Wait-HttpOk -Url "http://localhost:$FrontendPort/health" -TimeoutSeconds $TimeoutSeconds | Out-Null
Write-Host "OK: http://localhost:$FrontendPort/health"

Write-Host 'All checks passed.'
