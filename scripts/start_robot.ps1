param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$Esp32Url = "http://192.168.1.147",
  [string]$OllamaModel = "gemma4:e4b",
  [string]$OllamaUrl = "http://127.0.0.1:11434/api/generate",
  [int]$BackendPort = 5000,
  [int]$WebPort = 8080
)

$ErrorActionPreference = 'Stop'

function Test-PortListening {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return $null -ne $conn
}

$logsDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logsDir)) {
  New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$venvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
  throw "Environnement Python introuvable: $venvActivate"
}

# 1) Ollama
if (-not (Test-PortListening -Port 11434)) {
  Write-Host "[START] Ollama..."
  Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized `
    -RedirectStandardOutput (Join-Path $logsDir "ollama.out.log") `
    -RedirectStandardError (Join-Path $logsDir "ollama.err.log")
  Start-Sleep -Seconds 2
} else {
  Write-Host "[OK] Ollama déjà actif sur 11434"
}

# 2) Backend Flask
if (-not (Test-PortListening -Port $BackendPort)) {
  Write-Host "[START] Backend Flask..."
  $backendCmd = @"
Set-Location '$ProjectRoot'
. '$venvActivate'
`$env:OLLAMA_URL = '$OllamaUrl'
`$env:OLLAMA_MODEL = '$OllamaModel'
`$env:ESP32_URL = '$Esp32Url'
python .\robot_server.py
"@

  Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $backendCmd
  ) -WindowStyle Minimized `
    -RedirectStandardOutput (Join-Path $logsDir "backend.out.log") `
    -RedirectStandardError (Join-Path $logsDir "backend.err.log")

  Start-Sleep -Seconds 2
} else {
  Write-Host "[OK] Backend déjà actif sur $BackendPort"
}

# 3) Web app static server
if (-not (Test-PortListening -Port $WebPort)) {
  Write-Host "[START] Web app server..."
  $webRoot = Join-Path $ProjectRoot "mobile_webapp"
  $webCmd = "Set-Location '$webRoot'; python -m http.server $WebPort --bind 0.0.0.0"

  Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $webCmd
  ) -WindowStyle Minimized `
    -RedirectStandardOutput (Join-Path $logsDir "web.out.log") `
    -RedirectStandardError (Join-Path $logsDir "web.err.log")

  Start-Sleep -Seconds 1
} else {
  Write-Host "[OK] Web app déjà active sur $WebPort"
}

Write-Host ""
Write-Host "=== NEO démarré ==="
Write-Host "Backend : http://127.0.0.1:$BackendPort/health"
Write-Host "Web app : http://127.0.0.1:$WebPort"
Write-Host "Téléphone : http://<IP_PC>:$WebPort"
Write-Host "ESP32 URL : $Esp32Url"
Write-Host "Logs     : $logsDir"
