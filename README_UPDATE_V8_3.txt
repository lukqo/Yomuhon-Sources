Yomuhon-Sources v8.3 / MangaKatana v7

Replace the files in this package preserving their repository paths.

Changes:
- keeps declarative Popular + 9 real MangaKatana genres from v6
- bumps MangaKatana to v7
- fixes the page-image regex so it matches both https:// and JavaScript-escaped https:\/\/ URLs
- keeps page/image hosts restricted by allowedDomains
- keeps the identity metadata schema/docs from v8

Validate:
  python3 scripts/validate_sources.py
  python3 scripts/validate_sources.py --live --source mangakatana_json

The live command must pass Search -> Detail -> Chapters -> Pages -> First image before v7 should be considered fully verified.
