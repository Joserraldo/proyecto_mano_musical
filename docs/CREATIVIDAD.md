# 🎨 Puntos de creatividad

Ideas que hacen de Mano Musical algo más que "un piano con cámara". Se marcan
las ya implementadas ✅ y las propuestas 🚧.

---

## Implementadas

### ✅ Air-piano sin contacto
El instrumento es **el gesto**, no la tecla. Bajas un dedo en el aire y suena.
No hay superficie, no hay pulsación física: puro tracking.

### ✅ Diez dedos, diez notas afinadas
La escala C4–E5 (Do a Mi agudo) calza con la melodía de Jingle Bells.
Manos "desplegadas" con los pulgares al centro para que los saltos caigan cerca.

### ✅ Dinámica por velocidad de gesto
`|Δángulo|/Δt` se mapea a volumen: un dedo que baja decidido suena fuerte y uno
que baja suave suena piano. Da expresividad sin pedales ni MIDI velocity.

### ✅ Acordes reales
Cada dedo ocupa su canal de `pygame.mixer`, así varios dedos suenan a la vez
(por ejemplo Do+Mi+Sol con la izquierda). Ideal para acompañar la melodía.

### ✅ Timbres en vivo
`T` cicla `piano → organ → chiptune → synth`, cada uno con distinta mezcla de
armónicos y decaimiento. Cambia el carácter de la misma partitura.

### ✅ Partículas reactivas
Cada nota dispara un estallido en la yema que la tocó, con **el color de la nota**
(Do rojo, Mi amarillo, La azul...). Feedback visual inmediato.

### ✅ Esqueleto de mano en vivo
Se dibujan las 21 conexiones; los huesos se iluminan cuando su dedo toca.
Útil para depurar el tracking y estéticamente potente.

### ✅ Modo juego (ritmo)
Notas que caen, línea de golpe, juicio Perfect/Good/OK/Miss, combo y precisión.
Convierte practicar en jugar.

### ✅ Grabación y replay
`R` graba tu performance a JSON (`recordings/`). `F4` la reproduce en bucle,
con audio y partículas. Puedes compartir el JSON.

### ✅ Transposición por octava
`O` sube/baja 12 semitonos en vivo. La misma digitación suena una octava arriba.

### ✅ Degradación elegante (accesibilidad)
Sin cámara o sin MediaPipe, el teclado `A S D F G H J K L ;` es el piano.
También sirve para ensayar la digitación sin cansar los brazos.

### ✅ Detección con dos estrategias
`curl` (doblar el dedo) y `drop` (bajarlo), alternables con `[` / `]`.
Se adapta a distintas manos, luces y cámaras.

---

## Propuestas (roadmap creativo)

### 🚧 Calibración guiada
Al arrancar, pedir "mano abierta" 3 segundos para fijar la línea base de cada
dedo y afinar umbrales por usuario (útil para manos grandes/pequeñas).

### 🚧 Profundidad (`z`) para el modo drop
Usar la componente Z de MediaPipe para detectar el dedo "hacia la cámara",
permitiendo tocar con un gesto más cercano al de pulsar.

### 🚧 Acompañamiento automático
Generar bajo + batería sintetizados y sincronizados; el usuario toca solo la
melodía sobre una base. Ya existe `AudioEngine.play_backing` para alimentarlo.

### 🚧 Dos jugadores
Una mano por jugador, o un jugador por mano. Puntaje comparado.

### 🚧 Exportar a MIDI/WAV
Convertir la performance grabada a `.mid` (para editar) y `.wav` (para compartir).

### 🚧 Letra / karaoke
Mostrar la sílaba sincronizada ("Jin-gle bells...") mientras caen las notas.

### 🚧 Efectos por gesto
- Mano abierta sostenida = **sustain**.
- Puño = **mute**.
- Swipe horizontal = **cambio de canción** (el `SwipeDetector` ya existe).

### 🚧 Editor de partituras
Interfaz para escribir canciones y guardarlas como JSON, más carga de MIDI.

### 🚧 Modo "aprende conmigo"
La canción espera a que toques la nota correcta (sin castigo de tiempo),
ideal para principiantes antes del modo juego.

### 🚧 Zona de percusión
Asignar la parte baja del cuadro a "golpes" (batería) detectando el descenso
rápido de la mano, para acompañar con ritmo.

---

## Por qué esto es "creatividad" y no solo features

1. **Reinterpreta el instrumento**: el cuerpo (los dedos) es la interfaz.
2. **Da retorno expresivo**: color, partículas, sonido y puntaje en milisegundos.
3. **Se adapta al usuario**: dos modos de detección, transposición, timbres, teclado.
4. **No depende de assets**: la música se genera y las canciones son datos.
5. **Es jugable y compartible**: modo juego + grabación/replay.
