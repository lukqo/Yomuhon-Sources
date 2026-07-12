Yomuhon-Sources update for Yomuhon app v8.2
Date: 2026-07-12

Replace these paths in the existing Yomuhon-Sources repository:

- index.json
- sources/mangakatana.json
- schemas/source-schema-v1.json
- scripts/validate_sources.py
- tests/mangakatana.test.json
- docs/discover-contract.md
- docs/identity-metadata-contract.md

This publishes MangaKatana definition v6 with:
- real Hot Manga popular discovery
- real declarative genres
- v4 chapter-selector fixes preserved

It also publishes the identity metadata schema used by app v8.x.

After copying the files into the repository, run from repository root:

python3 scripts/validate_sources.py

Expected static result:
STATIC OK: 3 source(s), 3 live test definition(s)

Then commit and push to main. Yomuhon reads main/index.json and the source definitions referenced by it.
