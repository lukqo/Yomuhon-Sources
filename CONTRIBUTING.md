# Contributing to Yomuhon Sources

This repository holds declarative source definitions consumed by
[Yomuhon](https://github.com/lukqo/Yomuhon). It does not contain Swift, JS or
any executable remote code — only `html` / `json-api` declarative definitions.
Contributions to add or fix a source are very welcome.

## Requirements

- Python 3.10+

## Adding a new source

1. Fork and clone the repo.
2. Generate a starting point:
   ```bash
   python3 scripts/new_source.py <source-id>
   ```
3. Fill in the definition in `sources/<source-id>.json` using either the
   `html` or `json-api` runtime — see `schemas/source-schema-v1.json` for the
   schema and existing files in `sources/` for examples.
4. Add a regression definition in `tests/<source-id>.test.json`.
5. Validate locally:
   ```bash
   python3 scripts/validate_sources.py
   ```
6. A source is published as `stable` only after passing Search → Detail →
   Chapters → Pages → First image manually. New or unproven sources stay
   `testing`. Don't mark a source `stable` yourself unless you've verified
   the full flow — say so in the PR and let it get reviewed as `testing`.
7. Keep the same version number in `index.json` and in the source's own
   config, and keep domains consistent between the two.
8. See `docs/publication-semantics.md` for how `index.json`, `enabled` and
   `enabledByDefault` interact before touching those fields.

## Fixing a broken source

Sites change their markup/API often. If a source stops working:

1. Open an issue (or check if one exists) describing what broke.
2. Update the relevant JSON in `sources/`, keeping the schema valid.
3. Update or add the matching `tests/<source-id>.test.json` regression case.
4. Run `python3 scripts/validate_sources.py` before opening the PR.

## Submitting a PR

- One source (add or fix) per PR — makes review much faster.
- CI runs `validate-sources.yml` automatically; make sure it's green.
- Describe what you tested manually (Search/Detail/Chapters/Pages/First
  image) in the PR description.

## Code of conduct

Be respectful and constructive. Please don't submit definitions that bypass
anti-bot protections or that point at sources hosting content without rights
to distribute it.
