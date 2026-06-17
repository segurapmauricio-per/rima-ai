# Inicia RIMA en http://localhost:8000 (mata instancias previas primero).
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

& "$PSScriptRoot\stop_rima.ps1" | Out-Null
Start-Sleep -Seconds 1

Write-Host "Iniciando python main.py en $Root ..." -ForegroundColor Cyan
python main.py
