$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker não foi encontrado. Instale e inicie o Docker Desktop antes de continuar."
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "O Docker Desktop não está iniciado ou o mecanismo Linux ainda não está pronto."
}
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose v2 não está disponível nesta instalação."
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes)
    $rng.Dispose()
    @("API_KEYS=", "SEARXNG_SECRET=$secret") | Set-Content -Path (Join-Path $Root ".env") -Encoding ASCII
    Write-Host "Arquivo .env local criado com segredo aleatório."
}

Write-Host "Baixando/iniciando Siftdog e SearXNG..."
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "Falha ao iniciar os contêineres do Siftdog." }

$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3
        if ($health.status -eq "ok") { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    docker compose ps
    throw "Siftdog não respondeu em 120 segundos. Verifique os logs com: docker compose logs"
}
Write-Host "Siftdog está pronto em http://127.0.0.1:8000"
