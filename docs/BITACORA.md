# Bitácora de desarrollo — Mano Musical

Diario técnico del proyecto. Registra decisiones, obstáculos y verificaciones,
en orden cronológico. La idea es que cualquiera (incluido yo en el futuro)
entienda **por qué** el código está como está.

---

## 2026-10-02 · Sesión 1 — Fundaciones

### 1. Reconocimiento del entorno

Comandos ejecutados y hallazgos:

```
python --version        -> Python 3.12.10
pip --version           -> BLOQUEADO (Application Control policy)
python -m pip --version -> pip 26.2.1  ✅ (workaround obligatorio)
git --version           -> 2.55.0
cv2 4.13.0              -> ya instalado
numpy 2.2.6             -> ya instalado
mediapipe / pygame      -> FALTABAN
```

**Decisión:** documentar en README que en este equipo hay que usar siempre
`python -m pip` porque `pip.exe` es bloqueado por la política de Windows.

### 2. Elección de librerías

- **MediaPipe** para manos: es el estándar, da 21 landmarks y corre en CPU.
- **OpenCV** para captura de cámara.
- **pygame** para ventana + mixer de audio (pedido explícito del usuario).

Se instaló `mediapipe 1.0.1`, que **trajo `sounddevice` y `opencv-contrib-python 5.0`**
como dependencias. `cv2` subió a 5.0.0.93 (compatible).

### 3. Sorpresa: MediaPipe 1.x rompió la API clásica

Verificación:

```python
import mediapipe as mp
hasattr(mp, 'solutions')  # -> False
dir(mp)                   # -> ['Image', 'ImageFormat', 'tasks']
```

MediaPipe 1.0 **eliminó** `mp.solutions.hands`. La API nueva es
`mediapipe.tasks.python.vision.HandLandmarker`, en modo `VIDEO`, que además
exige un archivo de modelo `.task`.

**Decisión:**
- Usar `HandLandmarker` con `running_mode=RunningMode.VIDEO` y `detect_for_video(frame, ts_ms)`.
- Descargar el bundle oficial `hand_landmarker.task` (7.8 MB) a `assets/models/`.
- Dejar el modelo en `.gitignore` y proveer `scripts/download_models.py` + descarga automática (`utils.ensure_model`).

Verificado: `RunningMode.VIDEO`, `HandLandmarker.detect_for_video` y
`BaseOptions` existen en la 1.0.1.

### 4. Diseño musical: ¿por qué 10 notas y no 8?

El usuario pidió "un octeto o 10" y mencionó Jingle Bells. Se analizó la melodía:
en Do mayor usa **C4, D4, E4, F4, G4, A4, B4, C5, D5, E5** — exactamente 10 notas
(de C4 a E5). Coincidencia perfecta con 10 dedos.

**Mapa elegido** (notas suben de izquierda a derecha, pulgares al centro):

```
Izq: meñique C4 · anular D4 · medio E4 · índice F4 · pulgar G4
Der: pulgar A4 · índice B4 · medio C5 · anular D5 · meñique E5
```

Es ergonómico: los pulgares (centro) quedan en G4/A4 y las melodías que saltan
de G a C/D/E caen de forma natural.

### 5. Detección de "dedo bajado"

Primer intento mental: comparar la `y` del tip contra una línea base. Problema:
depende de la distancia a la cámara y de la orientación de la mano.

**Solución implementada:** ángulo de la articulación **PIP** entre `(MCP, PIP, TIP)`.
Es invariante a escala y rotación. Dedo extendido ≈ 180°, doblado ≈ 60–90°.

- **Histéresis**: entra en "presionado" con ángulo < 118° y sale con > 145°.
  Evita parpadeo cuando el dedo queda en el umbral.
- **Suavizado**: EMA sobre landmarks y sobre el ángulo.
- **Debounce**: mínimo 50 ms entre cambios por dedo.
- **Modo `drop`** como alternativa: normaliza el descenso del tip por el tamaño
  de la palma y lo compara con una línea base adaptativa.

**Velocidad**: se estima con `|Δángulo|/Δt` y se mapea a volumen (0.55–1.0).
Un dedo que baja rápido suena más fuerte.

### 6. Arquitectura multi-hilo

Pedido: "pygames para correr varios hilos y todo eso bien pro". Diseño:

| Hilo | Responsabilidad | Por qué |
|------|-----------------|---------|
| Principal | pygame (render + eventos + audio triggers) | el display debe vivir en el main thread |
| `CameraThread` | leer cámara | I/O bloqueante no debe frenar el render |
| `InferenceThread` | MediaPipe + gesto | CPU pesada, aislada |

Comunicación: `SharedState` con `Lock` para el último frame/hand_frame y una
`queue.Queue` para los eventos de nota. El hilo de inferencia descarta frames
viejos comparando `frame_id` (no acumula latencia).

### 7. Motor de audio polifónico

`pygame.mixer` por defecto mezcla en pocos canales. Se configuró
`set_num_channels(32)` y se implementó `AudioEngine` con un **canal por voz**
(`mano:dedo`). Las muestras se **sintetizan** (no se descargan assets):

- suma de armónicos (1, 0.5, 0.28, 0.14, 0.07),
- *detune* por armónico (efecto chorus),
- vibrato de ~5 Hz,
- envolvente ataque 8 ms + caída exponencial,
- normalización y conversión a `int16` estéreo.

Al soltar, `channel.fadeout(140ms)` evita clicks.

### 8. Modo juego y demo

- `Game` reutiliza la `Song` y crea objetivos con tiempo; ventanas
  Perfect (90 ms) / Good (200 ms) / OK (320 ms).
- `SongPlayer` es el autoplay para el modo demo.
- `PerformanceRecorder` guarda `(t, nota, velocidad, on/off)` a JSON en `recordings/`.

### 9. Verificación

```
python -m pytest -q     ->  32 passed
```

Smoke test headless (`SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`):

```
[INFO] audio: Mixer iniciado: (44100, -16, 2)
[INFO] tracker: HandTracker listo (máx 2 manos)
[INFO] app: Iniciando Mano Musical (mode=demo, cámara=False)
APP_EXIT_CODE 0
```

`HandTracker.process` sobre frame en negro: 0 manos, sin excepciones.

Un test de gesto falló al inicio: al volver el dedo a extendido, el suavizado
temporal (EMA 0.6) necesitaba ~4 frames para superar el umbral de liberación.
**No es un bug, es la histéresis funcionando.** Se ajustó el test para simular
varios frames, que es lo que pasa en la vida real a 30 fps.

### 10. Pendientes / ideas para la próxima sesión

- Calibración guiada al inicio (capturar "mano abierta" del usuario).
- Usar la componente `z` para el modo `drop` real (acercar/alejar el dedo).
- Backing track con bajo + batería.
- Exportar performance a WAV/MIDI.
- Backend de audio alternativo con `sounddevice` (ya instalado) para menor latencia.

---

## Plantilla para nuevas entradas

```
## AAAA-MM-DD · Sesión N — Título
### Objetivo
### Qué se intentó / obstáculos
### Decisión y por qué
### Verificación (comandos + resultado)
### Pendientes
```
