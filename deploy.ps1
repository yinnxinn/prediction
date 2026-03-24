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

Write-Host "[deploy] 构建镜像并启动容器（端口 8001）..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    docker-compose up -d --build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "[deploy] 完成。访问 http://127.0.0.1:8001/  （API 文档见 /docs）" -ForegroundColor Green
