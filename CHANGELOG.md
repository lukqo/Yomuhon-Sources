# Changelog

## 2026-07-27 — Restore sources deleted by accident (again) + stop silent breakage

- Same failure class as 2026-07-26, recurring: the two `new` commits made on 2026-07-27 (`de3ae31`, `ecbb1af`) deleted `lectormanga_es.json`, `mangadex.json`, `mangakatana.json`, `mangapill.json`, `webtoon_de.json`, `webtoon_en.json`, `webtoon_es.json`, `webtoon_fr.json`, `webtoon_id.json`, `webtoon_th.json`, `webtoon_zh_hant.json`, `leermanga.json`, `olympusbiblioteca.json` and their matching `tests/*.test.json` files (plus `zonatmo.test.json`, deleted earlier and never restored), again without touching `index.json`. `python3 scripts/validate_sources.py` would fail immediately with `Missing file: sources/lagoonscans.json` (or the next missing entry), and 14 of 15 catalog entries pointed at 404s on raw.githubusercontent.com — so the app could only ever load `zonatmo_es`, and even that only if a device had no stale cache.
- Restored all 14 missing source/test file pairs verbatim from the last commit where each existed (`ecbb1af^` for `lagoonscans.json`/`.test.json`, `de3ae31^` for everything else). No selectors changed. `id`/`name`/`version`/`language`/`engineMode` on every restored file match its `index.json` entry exactly, and `allowedDomains` still cover each `baseURL` host.
- Root cause both times: whatever local process is used to add/update a single source file is regenerating/committing the whole `sources/` and `tests/` directories from an incomplete local checkout instead of touching only the changed file, and the change is pushed without running `scripts/validate_sources.py` first. Until that workflow is fixed, this will keep recurring. Recommended fix: run `python3 scripts/validate_sources.py` locally (it fails loudly and immediately on any missing/mismatched file) before every commit that touches `index.json` or `sources/**`, and never edit `sources/**` from a shallow/partial local clone.

## 2026-07-27 — Per-source content-type discovery (`discover.types`)

- Added an optional `discover.types` block, mirroring `discover.genres`: a source declares its own content-type taxonomy (Manga/Manhwa/Manhua/Novela/etc.) instead of the app assuming a fixed enum. `supports.types: true` requires `discover.types`; both are optional so existing configs decode unchanged.
- Unlike genre IDs, type IDs are **not** canonical across sources — the app never fuses types from different sources into one list, only within each source's own catalog. `schemas/source-schema-v1.json` and `scripts/validate_sources.py` gained matching `typeItem`/`typeDiscovery` defs, static validation, and `--live` probe support (`minTypeResults`/`typeID` in test files).
- `zonatmo_es`: added `discover.types` with the site's real "Tipo" filter (Manga/Manhwa/Manhua/Webtoon/Novela/Comic/One shot/Doujinshi/OEL). Only the `manga`/`manhwa`/`manhua` values are confirmed (they appear directly in the site's own `/library/<value>/...` URLs); the `type` query parameter name and the remaining values are a best-effort guess. Run `python3 scripts/validate_sources.py --live --source zonatmo_es` before trusting this beyond `testing`.
- `docs/discover-contract.md` updated with a `types` section and the caveat above.

## 2026-07-26 — Restore sources deleted by accident + disable dead MangaEsp domain

- The "update" commit that renamed `mangapill.json`→`lagoonscans.json` and `lectormanga_es.json`→`mangaesp.json` also deleted `mangadex.json`, `mangakatana.json`, `mangapill.json`, `lectormanga_es.json`, `zonatmo.json` and all `webtoon_*.json` source/test files, without removing their entries from `index.json`. Static validation was broken (`Missing file: sources/lectormanga_es.json`) and 10 of 12 catalog entries pointed at 404s on raw.githubusercontent.com.
- Restored all 10 source/test file pairs from the last commit before the deletion (`ffcaefc`). No selectors changed; `python3 scripts/validate_sources.py` now passes again (`STATIC OK: 14 source(s), 14 live test definition(s)`).
- Disabled `mangaesp` (`enabled: false`): `mangaesp.topmanhuas.org` now returns a hosting-provider parking page instead of the manga site — the domain appears to have been reassigned. Needs a working domain before re-enabling.
- `lagoonscans.com` confirmed live; still a WordPress/Madara-family theme, chapter URL slugs match the source's `chapter-([0-9]+)` regex. Recommend running `--live --source lagoonscans` to confirm the full Search → Detail → Chapters → Pages → First image chain before promoting it out of `testing`.

## 2026-07-25 — WEBTOON notes cleanup

- Removed the "requires Yomuhon v12 or newer" claim from all `webtoon_*` entries: the app's only real version gate is `index.minimumAppVersion` (semver), and no such v12 check exists in the current app code — the note was stale/inaccurate.
- Fixed `webtoon_en` and `webtoon_es` notes, which were still saying "Keep disabled until live validation passes" despite both being `enabled: true` already.
- No source config or enabled/disabled state changed — text only.

## 2026-07-25 — Two new MangaThemesia sources

- Added `lagoonscans` (English) and `mangaesp` (Spanish), both mapped from the public MangaThemesia HTML theme they run on.
- Both register as `testing`/`experimental`, with selectors mirroring the theme's default markup — unverified against each domain's live HTML and pending live validation before wider use.

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

## 2026-07-21 — WEBTOON multilingual source batch

- Added the hybrid operation contract and seven staged WEBTOON language sources.
- New sources remain disabled until live validation succeeds.
