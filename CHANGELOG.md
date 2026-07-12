# Changelog

## 2026-07-11 — Authoring workflow

- Added `scripts/new_source.py` to scaffold and register HTML or JSON API sources.
- Added HTML and JSON API source templates plus a test template.
- Expanded README with a five-minute source-authoring workflow.
- Expanded the source authoring contract and troubleshooting guide.
- Hardened static validation for runtime mode, domains, selectors, capabilities, pagination and orphaned files.
- Added GitHub Actions static validation and 12-hour live validation with an uploaded report.

## 2026-07-11

- MangaDex v2: paginación de capítulos guiada por respuesta (`total`, IDs nuevos y fin de página).
- `maxItems` pasa a ser un límite defensivo; se elimina `maxPages` de la definición activa de MangaDex.


## 2026-07-11
- Add declarative `json-api` source kind.
- Move MangaDex discovery/configuration to the repository.
- Yomuhon no longer requires a bundled MangaDex adapter.
