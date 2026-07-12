# Source authoring

Yomuhon executes declarative source definitions. The repository describes providers; it does not ship provider-specific Swift or remote executable code.

## Engines

A source uses one of these `engineMode` values:

- `html`: routes plus the supported CSS subset and declarative page extractors.
- `json-api`: GET requests, JSON paths, pagination and URL templates.

The index entry must use the matching `kind`:

- `declarative-html`
- `declarative-json-api`

## Create a source

```bash
python3 scripts/new_source.py \
  --id my_source \
  --name "My Source" \
  --language en \
  --engine html \
  --base-url https://example.com
```

For JSON APIs use `--engine json-api`.

The generator creates a source definition, a test definition and registers the source in `index.json` as `testing`. Generated routes and mappings are skeletons and must be replaced with real provider behavior before live validation.

## Required release flow

1. Edit `sources/<id>.json`.
2. Edit `tests/<id>.test.json` with a stable probe.
3. Keep `enabledByDefault` false; the app owns local availability.
4. Run `python3 scripts/validate_sources.py`.
5. Run `python3 scripts/validate_sources.py --live --source <id>`.
6. Verify Search → Detail → Chapters → Pages → First image in Yomuhon.
7. Keep the source `testing` until the full flow is stable.
8. Increase the version in both the source config and `index.json` for every published mapping, route, selector or domain change.

## HTML selector subset

Supported forms include:

```text
tag
.class
#id
tag.class
tag[attr]
tag[attr='value']
tag[attr*='fragment']
tag:has(.descendant)
descendant selector
selector, selector
```

`:has(...)` accepts one simple descendant selector. Do not use unsupported pseudoclasses or the `>`, `+` and `~` combinators.

HTML sources may also declare `htmlScope` around a list operation and page extractors based on CSS or regex. Every emitted navigation or image host must be covered by `allowedDomains`.

## JSON API runtime

Schema v1 supports declarative GET operations, query parameters, repeated arrays such as `translatedLanguage[]`, JSON paths, response-driven pagination and URL templates.

Common templates include:

```text
{{query}}
{{languages}}
{mangaID}
{chapterID}
{baseURL}
{hash}
{item}
```

Chapter pagination continues while the provider returns new IDs and stops on empty responses, short pages, a reached `totalPath`, repeated pages or stalled IDs. `maxItems` is a defensive ceiling, not a normal chapter limit.

Identity metadata may declare alternative-title paths and year metadata. These fields help the app conservatively group the same work and route per-title language selection across providers.

## Discover and genres

A source only participates in a capability it explicitly declares. Popular and genre operations are optional.

Genres use a canonical app-facing `id` plus a provider-specific `value`. The app asks only sources that declare the selected genre and executes the provider mapping declaratively. Do not implement genre buttons as `search("Action")`.

See `docs/discover-contract.md` and `docs/identity-metadata-contract.md` for the extended contract.

## Validation

Install dependencies:

```bash
python3 -m pip install -r scripts/requirements.txt
```

Static validation:

```bash
python3 scripts/validate_sources.py
```

Live validation:

```bash
python3 scripts/validate_sources.py --live --source mangapill_json
```

The live gate verifies a real flow:

```text
search → manga → chapters → pages → first image
```

GitHub Actions performs static validation on pushes and pull requests. The live workflow also runs on `main`, manually and on the scheduled interval defined in `.github/workflows/validate-sources.yml`.
