# Detiene RIMA en el puerto 8000 (incluye hijos de uvicorn --reload).
$ErrorActionPreference = "SilentlyContinue"

Write-Host "Deteniendo procesos RIMA (main.py / uvicorn)..." -ForegroundColor Yellow

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'main\.py|uvicorn main:app|multiprocessing\.spawn' } |
  ForEach-Object {
    Write-Host "  PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force
  }

Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  Where-Object { $_ -gt 0 } |
  ForEach-Object {
    Write-Host "  Puerto 8000 -> PID $_"
    Stop-Process -Id $_ -Force
  }

Start-Sleep -Seconds 1
$listening = netstat -ano | findstr ":8000" | findstr "LISTENING"
if ($listening) {
  Write-Host "Aviso: algo sigue en 8000:" -ForegroundColor Red
  Write-Host $listening
} else {
  Write-Host "Listo. Puerto 8000 libre." -ForegroundColor Green
}
