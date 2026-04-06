# NEO Local Robot Setup (PC + ESP32 en HTTP)

> Ce guide est pensé pour **tout faire en local sur ton PC** (Ollama, Flask, TTS),
> avec l'ESP32 connecté en Wi-Fi au même réseau et piloté en HTTP.

## 1) Architecture finale

- **Téléphone (web app)**: reconnaissance vocale (`Web Speech API`) puis `POST /ask` vers le PC.
- **PC local (Flask)**:
  1. reçoit le prompt,
  2. appelle **Ollama/Gemma**,
  3. force une réponse JSON structurée,
  4. génère `response.wav` (TTS pyttsx3),
  5. envoie `POST /action` vers l'ESP32.
- **ESP32**: exécute l'action physique servo (`turn_left`, `turn_right`, `nod`, `none`).

## 2) Pré-requis PC (local)

- Python 3.10+
- Ollama installé et démarré
- Modèle Gemma installé:

```bash
ollama pull gemma:4b
```

Installer les dépendances Python:

```bash
pip install -r requirements.txt
```

> Si `pyttsx3` pose problème audio selon ton OS, installe aussi les drivers système :
> - Linux Debian/Ubuntu : `sudo apt-get install espeak ffmpeg libespeak1`
> - macOS : voix natives déjà disponibles (NSSpeechSynthesizer)
> - Windows : SAPI5 est utilisé automatiquement

## 3) Préparer ton environnement local (important)

Depuis la racine du repo, crée un environnement virtuel :

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\\Scripts\\activate     # Windows PowerShell
pip install --upgrade pip
pip install -r requirements.txt
```

Vérifie qu'Ollama tourne sur ton PC :

```bash
ollama serve
```

Dans un 2e terminal :

```bash
ollama list
ollama run gemma:4b "Réponds en JSON: {\"text\":\"ok\",\"action\":\"none\"}"
```

## 4) Lancer le serveur Flask local

Depuis la racine du repo:

```bash
export ESP32_URL="http://192.168.1.50"   # IP locale de ton ESP32
export OLLAMA_MODEL="gemma:4b"
export OLLAMA_URL="http://127.0.0.1:11434/api/generate"
python robot_server.py
```

Le serveur écoute par défaut sur `http://0.0.0.0:5000`.

## 5) Récupérer l'IP locale du PC

### Linux
```bash
hostname -I
```

### macOS
```bash
ipconfig getifaddr en0
```

### Windows (PowerShell)
```powershell
ipconfig
```

Prends l'IP du réseau Wi-Fi local (ex: `192.168.1.10`).

## 6) Tester API du serveur local (sans téléphone)

```bash
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Tourne la tête à droite"}'
```

Réponse attendue:

```json
{
  "text": "...",
  "action": "turn_right",
  "audio_url": "http://PC_IP:5000/audio/response.wav"
}
```

Tu peux aussi tester l'audio généré directement dans ton navigateur :

```
http://127.0.0.1:5000/audio/response.wav
```

## 7) Mettre la web app sur ton téléphone

- Méthode simple en local : depuis `mobile_webapp/` lance un petit serveur web :

```bash
cd mobile_webapp
python -m http.server 8080
```

- Sur ton téléphone (même Wi-Fi), ouvre :
  - `http://PC_IP:8080`
- Dans le champ URL serveur, mets :
  - `http://PC_IP:5000`

- Alternative : publier `mobile_webapp/` sur GitHub Pages, puis garder l'URL Flask locale.
- Renseigne l'URL du serveur Flask avec IP LAN du PC: `http://PC_IP:5000`.
- Clique **Parler**, puis **Envoyer le texte**.
- Vérifie:
  - texte affiché,
  - action affichée,
  - audio qui se joue,
  - mouvement du servo sur ESP32.

### iPhone / Safari / Chrome iOS (important)

- Sur iOS, la Web Speech API est parfois indisponible.
- La nouvelle web app inclut un fallback:
  1. enregistrement audio via micro,
  2. envoi au backend `POST /transcribe`,
  3. transcription locale (faster-whisper),
  4. envoi automatique à `POST /ask`.

Installe la dépendance STT:

```bash
pip install faster-whisper
```

## 8) Flasher et tester ESP32 (Arduino IDE)

Fichier firmware: `wokwi/neo_http_robot.ino`

1. Ouvre Arduino IDE.
2. Installe les cartes **ESP32 by Espressif Systems**.
3. Installe les librairies :
   - `ESP32Servo`
   - `ArduinoJson`
4. Ouvre `wokwi/neo_http_robot.ino`.
5. Mets ton SSID/mot de passe Wi-Fi dans le `.ino`.
6. Sélectionne la bonne carte (ex: ESP32 Dev Module) + port série.
7. Compile puis flash.
8. Ouvre le moniteur série (115200) et note l'IP affichée.
9. Test direct:

```bash
curl -X POST http://ESP32_IP/action \
  -H "Content-Type: application/json" \
  -d '{"action":"nod"}'
```

Tu peux aussi vérifier la santé:

```bash
curl http://ESP32_IP/health
```

> Note: dans ce firmware HTTP minimal, l'écran OLED n'est pas piloté.
> Il peut rester noir tant que tu n'ajoutes pas une logique d'affichage.

## 9) Check-list de debug (si ça ne marche pas)

1. **Téléphone et PC sur le même Wi-Fi** (important).
2. Firewall du PC autorise le port `5000`.
3. Test depuis PC :
   - `curl http://127.0.0.1:5000/health`
4. Test depuis téléphone :
   - `http://PC_IP:5000/health`
5. Test ESP32 :
   - `curl http://ESP32_IP/health`
6. Test chaîne complète :
   - `POST /ask` puis vérifier mouvement servo.

## 10) Extension prévue (bonus)

Le firmware est prêt pour extension:

- placeholder configuration audio I2S (`AudioConfig`),
- ajout facile de nouvelles actions via `runAction`,
- synchronisation voix+mouvement côté Python (ajouter timeline d'actions avant/pendant TTS).
