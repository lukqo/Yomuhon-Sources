Yomuhon-Sources Discover v5 replacement bundle

Copy these paths over the same paths in the Yomuhon-Sources repository.

Changed:
- index.json
- sources/mangakatana.json
- schemas/source-schema-v1.json
- scripts/validate_sources.py
- tests/mangakatana.test.json
- docs/discover-contract.md (new)

The bundle is based on MangaKatana v4 selectors from commit 57a0801e2b8a83b4bbaee75e7e8ec2d350de5ff0 and only bumps that source to v5 for declarative discovery. MangaDex and MangaPill are not modified.

Validate after copying:

    python3 -m pip install -r scripts/requirements.txt
    python3 scripts/validate_sources.py
    python3 scripts/validate_sources.py --live --source mangakatana_json
