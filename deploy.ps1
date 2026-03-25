#Requires -Version 5.0
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

function Test-DockerAvailable {
    $null -ne (Get-Command docker -ErrorAction SilentlyContinue)
}

if (-not (Test-DockerAvailable)) {
    Write-Error "未检测到 Docker，请先安装 Docker Desktop 并确保 docker 在 PATH 中。"
}

if (-not (Test-Path .env)) {
    Write-Host "[deploy] 未找到 .env，已从 .env.example 复制；请编辑 .env 填入 LLM 等配置。" -ForegroundColor Yellow
    Copy-Item -Force .env.example .env
}

Write-Host "[deploy] 构建并启动（Nginx 80 → app:8001）..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    docker-compose up -d --build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "[deploy] 完成。" -ForegroundColor Green
Write-Host "  http://<服务器IP>/          页面与 API"
Write-Host "  http://<服务器IP>/docs      Swagger"
Write-Host "  日志: docker compose logs -f app"
Write-Host "  Nginx: docker compose logs -f gateway"
