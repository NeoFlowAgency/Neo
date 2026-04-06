param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$Esp32Url = "http://192.168.1.147",
  [string]$OllamaLightModel = "gemma4:e4b",
  [string]$OllamaHeavyModel = "qwen2.5:14b",
  [string]$OllamaUrl = "http://127.0.0.1:11434/api/generate",
  [int]$BackendPort = 5000,
  [Alias("JarvisMode","Jarvis","Jarvice")]
  [switch]$JarviceMode
)

$ErrorActionPreference = 'Stop'

function Test-PortListening {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return $null -ne $conn
}

function Test-JarviceRunning {
  $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "jarvice_mode.py"
  }
  return $null -ne $procs
}

$logsDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logsDir)) {
  New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$venvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
  throw "Environnement Python introuvable: $venvActivate"
}

if (-not (Test-PortListening -Port 11434)) {
  Write-Host "[START] Ollama..."
  Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized `
    -RedirectStandardOutput (Join-Path $logsDir "ollama.out.log") `
    -RedirectStandardError (Join-Path $logsDir "ollama.err.log")
  Start-Sleep -Seconds 2
} else {
  Write-Host "[OK] Ollama deja actif sur 11434"
}

if (-not (Test-PortListening -Port $BackendPort)) {
  Write-Host "[START] Backend Jarvis..."
  $backendCmd = @"
Set-Location '$ProjectRoot'
. '$venvActivate'
`$env:OLLAMA_URL = '$OllamaUrl'
`$env:OLLAMA_MODEL_LIGHT = '$OllamaLightModel'
`$env:OLLAMA_MODEL_HEAVY = '$OllamaHeavyModel'
`$env:ESP32_URL = '$Esp32Url'
`$env:PORT = '$BackendPort'
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
  Write-Host "[OK] Backend deja actif sur $BackendPort"
}

if ($JarviceMode) {
  if (Test-JarviceRunning) {
    Write-Host "[OK] Jarvice deja actif"
  } else {
    Write-Host "[START] Jarvice mode..."
    $jarviceCmd = @"
Set-Location '$ProjectRoot'
. '$venvActivate'
`$env:JARVICE_BACKEND = 'http://127.0.0.1:$BackendPort'
python .\\jarvice_mode.py
"@

    Start-Process -FilePath "powershell" -ArgumentList @(
      "-NoProfile",
      "-ExecutionPolicy", "Bypass",
      "-Command", $jarviceCmd
    ) -WindowStyle Minimized `
      -RedirectStandardOutput (Join-Path $logsDir "jarvice.out.log") `
      -RedirectStandardError (Join-Path $logsDir "jarvice.err.log")

    Start-Sleep -Seconds 1
  }
}

Write-Host ""
Write-Host "=== JARVIS demarre ==="
Write-Host "Dashboard : http://127.0.0.1:$BackendPort"
Write-Host "Health    : http://127.0.0.1:$BackendPort/health"
Write-Host "Mobile/LAN: http://<IP_PC>:$BackendPort"
Write-Host "ESP32 URL : $Esp32Url"
Write-Host "Models    : light=$OllamaLightModel | heavy=$OllamaHeavyModel"
Write-Host "Logs      : $logsDir"
if ($JarviceMode) {
  Write-Host "Jarvice   : actif (wake word local)"
} else {
  Write-Host "Jarvice   : inactif (ajoute -JarviceMode)"
}
