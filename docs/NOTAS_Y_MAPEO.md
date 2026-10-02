# 🗺️ Notas, dedos y frecuencias

Documento de referencia del mapeo entre **dedo → nota → frecuencia**. Es la
fuente de verdad de `src/mano_musical/config.py` (`NOTE_MAP` y `SCALE`).

---

## Escala de 10 notas (Do mayor, C4–E5)

Se eligió este rango porque es **exactamente** el que necesita Jingle Bells en
Do mayor, y coincide con 10 dedos.

| # | Nota | Solfeo | Frecuencia (Hz) | Mano | Dedo | Nombre dedo |
|:-:|:----:|:------:|:---------------:|:----:|:----:|-------------|
| 1 | C4 | Do | 261.63 | Izquierda | pinky | meñique |
| 2 | D4 | Re | 293.66 | Izquierda | ring | anular |
| 3 | E4 | Mi | 329.63 | Izquierda | middle | medio |
| 4 | F4 | Fa | 349.23 | Izquierda | index | índice |
| 5 | G4 | Sol | 392.00 | Izquierda | thumb | pulgar |
| 6 | A4 | La | 440.00 | Derecha | thumb | pulgar |
| 7 | B4 | Si | 493.88 | Derecha | index | índice |
| 8 | C5 | Do' | 523.25 | Derecha | middle | medio |
| 9 | D5 | Re' | 587.33 | Derecha | ring | anular |
| 10 | E5 | Mi' | 659.25 | Derecha | pinky | meñique |

> Frecuencias por temperamento igual partiendo de A4 = 440 Hz.
> Fórmula: `f = 440 · 2^((midi − 69)/12)` (`music.note_to_freq`).

---

## Representación

- **`config.SCALE`**: lista ordenada `["C4", ..., "E5"]`.
- **`config.NOTE_MAP`**: diccionario `(mano, dedo) → nota`, con mano `"Left"`/`"Right"`
  y dedo en `config.FINGER_ORDER = ["thumb", "index", "middle", "ring", "pinky"]`.
- **`config.VISUAL_KEYS`**: orden de las teclas dibujadas (idéntico a `SCALE`).
- **`config.KEYBOARD_MAP`**: respaldo de teclado (fila izquierda + fila derecha).

---

## Codificación de nombres

Notación científica anglosajona:

```
   C4   = do central (261.63 Hz)
   C5   = do una octava arriba
   Eb4  = mi bemol (sostenidos/bemoles soportados en el parser)
```

`music.note_to_midi("C4") == 60`, `music.midi_to_freq(69) == 440.0`.

---

## Por qué dedos "hacia afuera"

```
                    +
        G4 (pulgar izq)   A4 (pulgar der)
   F4 (índice)                 B4 (índice)
   E4 (medio)                   C5 (medio)
   D4 (anular)                  D5 (anular)
   C4 (meñique)                 E5 (meñique)
```

Los pulgares quedan en el **centro** (Sol/La) y las notas suben hacia afuera.
Esto hace que los saltos melódicos de Jingle Bells (`G→C→D→E`) se hagan con
dedos contiguos, sin cruzar las manos.

---

## Correspondencia con landmarks de MediaPipe

Cada dedo se calcula con 4 landmarks (índices 0–20):

| Dedo | Joints (MCP, PIP, DIP, TIP) | Ángulo de flexión |
|------|----------------------------|-------------------|
| pulgar | 1, 2, 3, 4 | min(∡ en 2, ∡ en 3) |
| índice | 5, 6, 7, 8 | ∡ en 6 (PIP) |
| medio | 9, 10, 11, 12 | ∡ en 10 (PIP) |
| anular | 13, 14, 15, 16 | ∡ en 14 (PIP) |
| meñique | 17, 18, 19, 20 | ∡ en 18 (PIP) |

`0 = muñeca`. El ángulo se mide con el producto punto de los vectores
`(MCP − PIP)` y `(TIP − PIP)`; es invariante a escala y rotación.

---

## Añadir más notas u octavas

1. Edita `config.SCALE` y `config.NOTE_MAP`.
2. Si superas 10 dedos, considera **cambiar de octava** con el gesto/tecla `O`.
3. La síntesis acepta cualquier nota válida: `music.synthesize_note_timbre("F#3")`.
