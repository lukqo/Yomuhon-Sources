# Source authoring

Una fuente usa `engineMode: html` o `engineMode: json-api`.

`html` define `routes` y `selectors`. `json-api` define `api.search`, `api.chapters` y `api.pages`. Las rutas API solo aceptan GET en schema v1. Los templates disponibles son `{{query}}`, `{mangaID}`, `{chapterID}`, `{{languages}}`, `{baseURL}`, `{hash}` y `{item}` según la operación.

## Paginación JSON API

Las operaciones de capítulos pueden declarar `pagination` con `offsetParam`, `limitParam` y `limit`. El runtime continúa pidiendo páginas mientras la API entregue IDs nuevos. Se detiene cuando la página viene vacía, trae menos elementos que `limit`, alcanza `totalPath`, repite una página o deja de entregar IDs nuevos.

`maxItems` es solo un techo defensivo contra una configuración o API defectuosa; no representa la cantidad normal de capítulos. `maxPages` sigue aceptándose únicamente por compatibilidad con configuraciones cacheadas antiguas y no se recomienda para fuentes nuevas.

Toda fuente debe declarar `allowedDomains`, subir su `version` al cambiar y tener un smoke test con resultados, capítulos y páginas reales.
