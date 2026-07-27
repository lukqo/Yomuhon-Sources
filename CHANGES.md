# Yomuhon-Sources — changes in this patch

Drop these files into the matching paths at your `Yomuhon-Sources` repo root,
overwriting the originals.

## 1. Schema + validator: new `dedupeByNumber` field

- `schemas/source-schema-v1.json`: added `dedupeByNumber: boolean` to
  `chapterSelector`.
- `scripts/validate_sources.py`: recognized `dedupeByNumber` as a plain flag
  (not a nested CSS selector) in static validation, and mirrored the same
  dedup behavior in `parse_html_chapters` so `--live` validation matches what
  the Swift runtime will actually do. I unit-tested this function standalone
  in this sandbox (BeautifulSoup is available; `jsonschema` is not, so I could
  not run `validate_sources.py` end-to-end — please run it yourself:
  `pip install -r scripts/requirements.txt && python3 scripts/validate_sources.py`).

## 2. `sources/zonatmo.json` — v1 → v2, real bug fix + context

**Why ZonaTMO doesn't work well, in one sentence:** the original TuMangaOnline
/ ZonaTMO (`zonatmo.com`) was shut down by Spanish police in March/April 2026
(four arrests, domain in registrar `clientHold`). `zonatmo.org`, the domain
your source points at, is one of several unaffiliated mirror sites that
appeared afterward — it is not the original operation, so its markup and
uptime aren't guaranteed to track what the selectors were originally mapped
against.

On top of that domain-risk issue, there was a real selector bug:
- `chapters.container` was a bare `"li"` — matches every `<li>` on the page,
  not just chapter rows (mitigated somewhat by the URL selector requiring a
  nested `/viewer/`, `/chapter/` or `/read/` link, but still noisy/fragile).
  Scoped it to `"li.upload-link, .chapters li, #chapters li, li"` (falls back
  to the old behavior if none of the more specific selectors match anything).
- No dedup by chapter number — TMO-style pages list the same chapter once per
  scanlation group, each at a different URL, so the reader showed duplicate
  "Capítulo N" rows. Added `dedupeByNumber: true`.

Bumped `version` in both `sources/zonatmo.json` and its `index.json` entry
(1 → 2) per your own release flow in `docs/source-authoring.md`. Updated the
`notes` field to record the domain-risk context above so future-you (or
anyone else touching this repo) doesn't have to rediscover it.

**I could not run `--live` validation** (no network access in this sandbox)
— please run `python3 scripts/validate_sources.py --live --source zonatmo_es`
before trusting this in production, exactly as your own docs already
prescribe for any selector change.

## 3. Restored `lagoonscans` (English scans, MangaThemesia/Madara theme)

This is not a new source I invented — it's recovery of work you already did.
Digging through `git log`, I found:

- `sources/lagoonscans.json` + `tests/lagoonscans.test.json` were added in
  commit `8a11324` ("update").
- They were deleted in the very next commit, `5f46361` ("update again bro"),
  along with `mangaesp`.
- Your `CHANGELOG.md` entry dated 2026-07-26 says both were "restored" and
  that `lagoonscans.com confirmed live" — but the commit that actually
  shipped (`72b77d0`, "bug arreglado") instead *removed* both entries from
  `index.json` entirely, without restoring the source/test files. So the
  changelog and the actual repo state disagree.

I restored `sources/lagoonscans.json` and `tests/lagoonscans.test.json`
byte-for-byte from commit `8a11324` (the last version before deletion), and
re-added its `index.json` entry with a note explaining the restore. I did
**not** restore `mangaesp` — your own 2026-07-26 changelog entry already
found that `mangaesp.topmanhuas.org` now serves a hosting-provider parking
page (domain reassigned), so re-adding a dead domain isn't useful.

Since this was "confirmed live" over 48 hours ago and site markup can drift,
re-run `--live --source lagoonscans` before treating it as stable again.

## 4. `index.json`

Reflects the version bump for `zonatmo_es` and the restored `lagoonscans`
entry. `updatedAt` bumped to 2026-07-27.

## What I did not add

I did not author a brand-new international scans source (e.g. Manganato/
Natomanga) from scratch in this pass, on purpose: recovering the source you
already built and validated once seemed like the better use of this round
than guessing blind at markup for a site I can't fetch from here. If you want
one, `python3 scripts/new_source.py --id manganato --name Manganato --language
en --engine html --base-url https://manganato.gg` gets you a skeleton in
seconds — domain-wise, manganato/natomanga are reported up as of late July
2026 but have a history of Cloudflare human-verification challenges and
domain moves (they moved from `.com` to `.gg` before), so validate live before
trusting it.
