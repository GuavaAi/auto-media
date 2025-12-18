param(
  [int]$Port = 8010,
  [switch]$Beat
)

$ErrorActionPreference = "Stop"

# 中文说明：
# - 该脚本用于本地开发一键启动：FastAPI(uvicorn) + Celery worker（可选 beat）
# - Windows 下 Celery 推荐使用 -P solo
# - 使用 Start-Process 新开窗口，避免相互阻塞

$root = Split-Path -Parent $PSScriptRoot
$backend = $root

Write-Host "Backend path: $backend"
Write-Host "Starting uvicorn on port $Port ..."
Start-Process -WorkingDirectory $backend -FilePath "powershell" -ArgumentList @(
  "-NoExit",
  "-Command",
  "uvicorn app.main:app --reload --port $Port"
)

Write-Host "Starting celery worker ..."
Start-Process -WorkingDirectory $backend -FilePath "powershell" -ArgumentList @(
  "-NoExit",
  "-Command",
  "python -m celery -A app.celery_app.celery_app worker -l info -P solo"
)

if ($Beat) {
  Write-Host "Starting celery beat ..."
  Start-Process -WorkingDirectory $backend -FilePath "powershell" -ArgumentList @(
    "-NoExit",
    "-Command",
    "python -m celery -A app.celery_app.celery_app beat -l info"
  )
}

Write-Host "Done. (Three PowerShell windows should be opened.)"
