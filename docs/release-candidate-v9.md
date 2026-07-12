# Source catalog release-candidate v9

This package consolidates the source repository required by the Yomuhon v9 internal release candidate.

## Resolved repository integrity issues

- all three index entries have a matching source JSON;
- all three source JSON files have a matching live-test definition;
- MangaKatana index/config versions both use v7;
- the index schema accepts both `declarative-html` and `declarative-json-api`;
- source authoring dependencies are declared in `scripts/requirements.txt`;
- `scripts/new_source.py` exists and registers new source skeletons;
- GitHub Actions performs static validation and scheduled/manual live validation.

## Validation boundary

`python3 scripts/validate_sources.py` is the deterministic release gate for repository structure and declarative contracts.

Live validation still depends on provider/network availability and must be run from a network that can resolve each provider.
