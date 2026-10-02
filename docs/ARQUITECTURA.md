# 🏗️ Arquitectura

Mano Musical separa **entrada (cámara)**, **entendimiento (IA/gesto)**,
**salida (audio)** y **presentación (pygame)** en componentes desacoplados.
Esto permite testear casi todo sin cámara ni dispositivo de audio.

---

## Diagrama de componentes

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              HILO PRINCIPAL (pygame)                         │
│                                                                              │
│   pygame events ──► ManoMusicalApp._handle_events                            │
│                         │                                                    │
│   SharedState.drain_events ──► _trigger_on/_trigger_off ──► AudioEngine      │
│                         │                              └──► Renderer        │
│   JingleBellsGame.update / SongPlayer.update / PerformancePlayer.update      │
│                         │                                                    │
│   Renderer.draw_* ──► pygame.display.flip()                                  │
└───────────────▲───────────────────────────────────────────┬─────────────────┘
                │ get_frame / get_hand_frame                 │ set_frame
                │ push_event                                 │ set_hand_frame
┌───────────────┴───────────────┐              ┌─────────────▼─────────────────┐
│      InferenceThread          │              │        CameraThread           │
│  HandTracker (MediaPipe)      │              │  cv2.VideoCapture + flip      │
│  FingerPressDetector          │              │  (publica el último frame)     │
│  ──► NoteTrigger ──► queue ───┘              └───────────────────────────────┘
└───────────────────────────────┘
```

- El **render** nunca espera a la IA: siempre dibuja el último frame/estado disponible.
- El hilo de inferencia **descarta frames viejos** comparando `frame_id`; si la IA
  va más lenta que la cámara, se salta frames en lugar de acumular latencia.

---

## Módulos

| Módulo | Responsabilidad | Depende de |
|--------|-----------------|------------|
| `config.py` | Constantes, rutas, mapa de notas, paleta | — |
| `music.py` | Teoría (nota↔MIDI↔freq), síntesis, `Song` | numpy, config |
| `audio_engine.py` | Polifonía sobre `pygame.mixer`, caché de samples | pygame, music |
| `hand_tracker.py` | Wrapper `HandLandmarker` (MediaPipe Tasks) | mediapipe, cv2 |
| `gesture.py` | Ángulos de dedo, histéresis, triggers, swipe | numpy, hand_tracker |
| `state.py` | `SharedState` seguro entre hilos | hand_tracker |
| `capture.py` | `CameraThread` + `InferenceThread` | cv2, gesture, hand_tracker |
| `render.py` | Cámara, esqueleto, teclas, partículas, HUD | pygame, config |
| `game.py` | `JingleBellsGame`, `SongPlayer` | music, config |
| `recorder.py` | Grabar/reproducir performances | config, json |
| `app.py` | Orquestador: bucle, modos, teclas | todos |
| `utils.py` | Logging, descarga de modelo, helpers | config |

### Flujo de datos de una nota (happy path)

```
frame BGR
  └─ CameraThread.set_frame(frame, ts)
        └─ InferenceThread: HandTracker.process(frame, ts) -> HandFrame(21×3 landmarks)
              └─ FingerPressDetector.update(HandFrame, now) -> [NoteTrigger(on, B4, vel=0.8)]
                    └─ SharedState.push_event(trigger)
                          └─ (hilo principal) drain_events -> AudioEngine.note_on("Right:index","B4",0.8)
                                                              -> Renderer.burst_note("B4", ...)
                                                              -> JingleBellsGame.register_input("B4", now)
```

---

## Decisiones clave

### 1. MediaPipe Tasks (no `mp.solutions`)
MediaPipe 1.x eliminó la API clásica. Se usa `HandLandmarker` en modo `VIDEO`
con `detect_for_video(image, timestamp_ms)`, que permite pasos síncronos desde
un hilo dedicado sin callbacks asíncronos.

### 2. Ángulo PIP en vez de posición
El gesto "dedo bajado" se detecta con el **ángulo de la articulación**, que es
invariante a la distancia y orientación de la mano. Complementado con:

- **EMA** en landmarks y en el ángulo (reduce temblor del tracking),
- **histéresis** (118° entra / 145° sale),
- **debounce** (50 ms),
- **normalización por tamaño de palma** en el modo `drop`.

### 3. Síntesis en vez de samples de audio
No hay `.wav` en el repo: cada nota se **genera** con armónicos + envolvente.
Ventajas: repo liviano, cualquier nota disponible, timbres intercambiables.
Costo: se renderiza una vez por (nota, timbre) y se cachea.

### 4. Estado compartido mínimo
Solo tres cosas cruzan hilos: el **frame** más reciente, el **HandFrame** más
reciente y la **cola de eventos**. El resto vive en el hilo principal. Menos
candados, menos bugs.

### 5. Degradación elegante
- Sin `mediapipe` → `HandTracker.available = False` y modo teclado.
- Sin cámara → `--no-camera` o apertura fallida → modo teclado/demo.
- Sin mixer → `AudioEngine.available = False`, la app sigue (muda).

---

## Puntos de extensión

- **Nueva canción**: agrega un JSON en `assets/songs/` y cárgalo con `music.load_song`.
- **Nuevo timbre**: añade una entrada a `music.Timbres` con `harmonics/decay/vibrato_cents`.
- **Nuevo modo de detección**: implementa otra rama en `FingerPressDetector._press_value`.
- **Nueva escala**: edita `config.SCALE` y `config.NOTE_MAP`.
- **Otro backend de audio**: implementa la misma interfaz que `AudioEngine`
  (`note_on/note_off/play_once/shutdown`) sobre `sounddevice`.

---

## Rendimiento

- Captura a 30 fps; render objetivo 60 fps (`config.TARGET_FPS`).
- `HandLandmarker` en CPU ~10–25 ms/frame según equipo (`stats.infer_ms` en el HUD).
- Mensajes de audio en `int16` mono→estéreo, buffer 512 (buen balance latencia/glitches).

---

## Pruebas sin hardware

- `tests/test_gesture.py` construye landmarks sintéticos: no necesita cámara.
- `tests/test_recorder.py` verifica `AudioEngine(enabled=False)`.
- Smoke test headless con `SDL_VIDEODRIVER=dummy` y `SDL_AUDIODRIVER=dummy`.
