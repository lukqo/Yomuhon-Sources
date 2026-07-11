# Changelog

## 2026-07-10 — Repository verification pass

- Added the real `mangapill_json` declarative source in testing state.
- Kept every remote source disabled by default inside Yomuhon.
- Added strict index/config/test consistency validation.
- Replaced syntax-only CI with search → details → chapters → pages → image smoke tests.
- Added a 12-hour GitHub Actions schedule and downloadable health report.
- Added a strict source schema and a dedicated index schema.
- Hardened MangaKatana cleanup against `[Cover]` titles and non-page images.

## 2026-07-10

- Documented the 12-hour automatic catalog refresh and health-check contract.
- Clarified consecutive-failure pausing and automatic recovery.
- Reserved manual source testing for diagnostics only.

## 2026-07-09

- Added source status metadata in `index.json`.
- Added the MangaKatana declarative source and tests.
- Added a Madara authoring template.
