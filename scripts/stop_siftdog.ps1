$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker não foi encontrado."
}
docker compose down
if ($LASTEXITCODE -ne 0) { throw "Falha ao encerrar os serviços do Siftdog." }
Write-Host "Siftdog e SearXNG encerrados. Imagens e configuração foram preservadas."
