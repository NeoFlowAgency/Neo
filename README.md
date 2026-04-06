# Jarvis V1

Version V1 recentree du projet pour un robot de bureau simple:

- PC Windows toujours allume comme cerveau local
- Ollama avec 2 niveaux de modeles
- backend Python unique
- ESP32 en HTTP pour servo, OLED et audio
- micro du PC en attendant le micro embarque

## Structure active

- `robot_server.py`: API locale Jarvis, memoire simple, STT, TTS, pilotage ESP32
- `mobile_webapp/index.html`: dashboard local minimal
- `wokwi/neo_http_robot.ino`: firmware ESP32 V1
- `scripts/start_robot.ps1`: demarrage local Windows
- `scripts/stop_robot.ps1`: arret local Windows
- `docs/local-robot-http-setup.md`: guide de mise en route

## Archive

L'ancien code `Neo` et les branches d'experimentation plus larges ont ete ranges dans:

- `archive/legacy-neo/`

Ils sont conserves a titre de reference mais ne font plus partie du chemin principal de `Jarvis V1`.

## Voix

La synthese vocale locale utilise maintenant `Kokoro ONNX`.

- modele local gratuit
- generation WAV cote PC
- envoi du fichier audio au robot via l'endpoint `/speak`
