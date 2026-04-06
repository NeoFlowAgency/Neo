# Jarvis V1 - Setup local Windows

Ce projet est maintenant recentre sur une architecture simple:

- `PC Windows` pour la conversation et l'IA locale
- `Ollama` pour les modeles
- `robot_server.py` pour l'API locale, la memoire simple et le pilotage du robot
- `ESP32` en HTTP pour le servo, l'OLED et l'audio

## Demarrage rapide

Depuis la racine du projet:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_robot.ps1 -Esp32Url "http://IP_DE_TON_ESP32"
```

Le dashboard sera disponible sur:

```text
http://127.0.0.1:5000
```

Sur le telephone, si tu es sur le meme Wi-Fi:

```text
http://IP_DE_TON_PC:5000
```

## Modeles par defaut

- modele leger: `gemma4:e4b`
- modele plus costaud: `qwen2.5:14b`

Tu peux les changer au lancement:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_robot.ps1 `
  -Esp32Url "http://IP_DE_TON_ESP32" `
  -OllamaLightModel "gemma4:e4b" `
  -OllamaHeavyModel "qwen2.5:14b"
```

## Endpoints utiles

- `GET /health`
- `GET /api/status`
- `GET /api/history`
- `POST /api/ask`
- `POST /api/transcribe`
- `POST /api/action`
- `POST /api/face`

## Firmware ESP32 actif

Le firmware V1 a flasher est:

- `wokwi/neo_http_robot.ino`

Il utilise:

- servo sur `GPIO 18`
- OLED I2C sur `SDA 21` et `SCL 23`
- MAX98357A sur `LRC 25`, `BCLK 26`, `DIN 27`

## Etat actuel

La pile locale est prete pour:

- transcription locale
- conversation locale via Ollama
- pilotage du servo
- expressions simples sur OLED
- dashboard local minimal

Le point restant a stabiliser est la sortie voix cote PC quand la pile TTS Windows n'a pas de voix disponible.
