# Contribuir a Mano Musical

¡Gracias por querer mejorar el proyecto! Estas son las reglas básicas.

## Entorno de desarrollo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
python scripts\download_models.py
```

> Si `pip.exe` está bloqueado por políticas de Windows, usa `python -m pip`.

## Antes de enviar un cambio

```powershell
python -m pytest -q          # 32 tests, deben pasar todos
python -m ruff check src tests   # lint (opcional pero recomendado)
```

## Estilo de código

- Python 3.10+.
- Formato consistente con el resto del repo; líneas de hasta 100 columnas (`ruff`).
- **Docstrings** en módulos, clases y funciones públicas.
- Evita comentarios de ruido; que el código se explique solo.
- Nombres de dominio en español (notas, dedos, modos) para mantener coherencia con `config.py`.

## Estructura de commits

[Conventional Commits](https://www.conventionalcommits.org/es/):

```
feat: agrega calibración guiada al inicio
fix: corrige swap de manos en cámara frontal
docs: amplía guía de Jingle Bells
test: cubre modo drop del detector
```

## Cómo añadir una canción

1. Crea `assets/songs/mi_cancion.json`:
   ```json
   {
     "name": "Mi Canción",
     "bpm": 100,
     "events": [
       { "note": "C4", "beats": 1 },
       { "note": null, "beats": 1 },
       { "note": "E4", "beats": 2 }
     ]
   }
   ```
2. Verifica que las notas pertenezcan a `config.SCALE` (o amplía la escala).
3. Cárgala con `music.load_song("assets/songs/mi_cancion.json")`.

## Cómo registrar tu trabajo

Si tomas decisiones técnicas relevantes, **añade una entrada a `docs/BITACORA.md`**
con objetivo, obstáculos, decisión y verificación. Es parte central del proyecto.

## Licencia

Al contribuir aceptas que tu aporte se publique bajo la licencia MIT del repositorio.
