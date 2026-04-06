param(
  [switch]$StopOllama
)

$ErrorActionPreference = 'SilentlyContinue'

Write-Host "[STOP] Backend robot_server.py"
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match "robot_server.py"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "[STOP] Web server (python -m http.server 8080)"
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match "python -m http.server 8080"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "[STOP] Jarvice mode (jarvice_mode.py)"
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match "jarvice_mode.py"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

if ($StopOllama) {
  Write-Host "[STOP] Ollama serve"
  Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "ollama serve"
  } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
}

Write-Host "Terminé."
