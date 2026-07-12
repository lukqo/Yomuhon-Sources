# Changelog

## 2026-07-12 — Public HTTPS runtime policy

- Treat `allowedDomains` as expected-host diagnostics instead of a hard block for dynamically discovered public CDN hosts.
- Keep a hard boundary around public HTTPS and reject localhost, local-only hostnames, private/link-local/loopback and other non-global literal IP destinations.
- Make the live validator warn on unexpected public hosts and continue the reading-path check.
- Reuse each source's declared network headers when validating the first page image, including `Referer` and `User-Agent` required by protected CDNs.

## 2026-07-12 — CI and publication semantics

- Restore `.github/workflows/validate-sources.yml` with static validation on relevant pushes and pull requests.
- Run live reading-path validation manually or every 12 hours on `main`, with the JSON report retained as a 14-day artifact.
- Document `index.enabled` plus `index.status` as the publication authority.
- Clarify that schema V1 `enabledByDefault: false` is a legacy compatibility sentinel, not a local activation gate.

## 2026-07-11 — MangaKatana v4

- MangaKatana v4 alinea búsqueda, popular, detalle y capítulos con las regiones de contenido mantenidas por la fuente.
- Los capítulos usan `tr:has(.chapter)` en vez de seleccionar todos los enlaces `/manga/` del documento.
- El validador acepta el subconjunto genérico `:has(<selector simple>)`.
- Una `number.regex` declarada pasa a ser autoritaria también en la validación live: los candidatos que no coinciden se descartan.

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
