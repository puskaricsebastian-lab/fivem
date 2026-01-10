# hayat-loading

## Installation
1. Ordner `hayat-loading` in deinen `resources`-Ordner legen.
2. In der `server.cfg` hinzufügen: `ensure hayat-loading`.

## Konfiguration (config/config.lua)
- **Servername & Texte:** `serverName`, `slogan`, `loadingTips`.
- **Farben:** `themeColor`, `secondaryColor`, `accentGlow`.
- **Hintergrundvideo:**
  - YouTube: `background.useYoutube = true` und `background.youtubeUrl` anpassen.
  - Lokal: `background.useYoutube = false` und `background.localVideoPath` setzen (Datei nach `html/assets/video/`).
- **Musik:**
  - YouTube: `music.useYoutube = true` und `music.youtubeUrl` anpassen.
  - Lokal: `music.useYoutube = false` und `music.localAudioPath` setzen (Datei nach `html/assets/music/`).
  - Anzeigename: `music.trackName`.
  - Standard-Lautstärke: `music.defaultVolume` (0.0–1.0).
- **Logo/Banner:**
  - `showLogo` + `logoFileName` (Datei in `html/assets/images/`).
  - `showBanner` + `bannerFileName` (Datei in `html/assets/images/`).
- **Discord:** `discord`.
- **Partikel/Snow:** `showSnow` (true/false).

## Hinweise zu YouTube Autoplay
Browser können Autoplay mit Sound blockieren. In diesem Fall startet die Musik stumm, obwohl ein automatischer Start versucht wird.
