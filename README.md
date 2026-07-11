# Yomuhon Sources

Repositorio de definiciones declarativas remotas para Yomuhon. La app ejecuta capacidades genéricas `html` y `json-api`; las fuentes se descubren desde `index.json` y no descargan código ejecutable.

## Paginación JSON API

Los feeds paginados usan `offsetParam`, `limitParam` y `limit`. El motor sigue consultando mientras aparezcan IDs nuevos y corta por respuesta vacía, página corta, `totalPath`, página repetida o ausencia de IDs nuevos. `maxItems` es únicamente un límite defensivo. `maxPages` queda reservado para compatibilidad con configuraciones antiguas.

Antes de publicar una fuente o subir su versión:

```bash
python3 -m pip install -r scripts/requirements.txt
python3 scripts/validate_sources.py
python3 scripts/validate_sources.py --live --source <source-id>
```
