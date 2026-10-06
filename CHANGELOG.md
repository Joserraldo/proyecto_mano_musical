# Changelog

Todos los cambios notables de este proyecto se documentan acá. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado
[SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Added
- Modo juego estilo piano tiles: carril por tecla y ladrillos con largo = duración de la nota.
- 4 canciones seleccionables con `1`-`4` (Jingle Bells, Estrellita, Campana sobre
  Campana, Cumpleaños Feliz), cada una con tempo base propio.
- 4 velocidades con `-`/`=` (multiplicador de BPM): lenta / normal / rápida / experta.
- Resumen al terminar la canción: score, precisión, combo máximo y conteo de juicios.
- `F12` guarda captura de pantalla en `docs/img/`; README con capturas reales.
- Controles en vivo: `X` invertir manos, `V` espejo, `B` rotar 180°, `,`/`.`
  sensibilidad, `C` calibración guiada.
- Calibración por dedo: mide el ángulo extendido real y deriva los umbrales
  (`ext_ref`); adapta el instrumento a cada mano.
- HUD de orientación y progreso de calibración.
- Flags `--rotate180` y `--no-swap-hands`.

### Fixed
- `--mode game` al arrancar no tiraba notas hasta pulsar SPACE (el conteo ahora
  inicia de inmediato).
- Crash al dibujar el esqueleto con numpy.float32 (`invalid start_pos argument`).
- Crash de audio cuando el dispositivo abre en 8 canales (muestra adaptada al
  número real de canales del mixer).
- `UnboundLocalError: velocity` en el detector al cambiar de dedo dentro del
  *debounce*.
- Doble inversión de manos (tracker + detector) que se cancelaba; ahora el swap
  se aplica solo en `HandTracker` y por defecto está activado.

## [1.0.0] - 2026-10-02

### Added
- Detección de manos en tiempo real con MediaPipe Tasks (`HandLandmarker`, modo VIDEO).
- Escala de 10 notas C4–E5 mapeada a los 10 dedos (`config.NOTE_MAP`).
- Detección de "dedo bajado" por ángulo PIP con histéresis, suavizado y debounce;
  modos `curl` y `drop`.
- Motor de audio polifónico propio sobre `pygame.mixer` con un canal por voz.
- Síntesis aditiva con armónicos, vibrato y envolvente ADSR; timbres
  `piano`, `organ`, `chiptune`, `synth`.
- Arquitectura multi-hilo: captura, inferencia y render desacoplados vía `SharedState`.
- Modo libre (air-piano), modo juego de Jingle Bells (notas que caen + puntaje),
  modo demo (autoplay) y modo replay.
- Grabación y reproducción de performances en JSON (`recordings/`).
- Render con cámara, esqueleto, teclado de 10 teclas, partículas y HUD.
- Modo sin cámara / accesibilidad con teclado (`A S D F G H J K L ;`).
- Partitura embebida y en `assets/songs/jingle_bells.json`.
- Descarga automática del modelo MediaPipe (`scripts/download_models.py`).
- Documentación: README, ARQUITECTURA, COMO_TOCAR, NOTAS_Y_MAPEO, CREATIVIDAD, BITACORA.
- Suite de 32 tests (música, gestos, juego, grabación).

### Notes
- Requiere Python 3.10–3.12.
- En equipos con `pip.exe` bloqueado por Application Control, usar `python -m pip`.
- El bundle `hand_landmarker.task` no se versiona; se descarga al primer uso.

[1.0.0]: https://github.com/TU_USUARIO/mano-musical/releases/tag/v1.0.0
