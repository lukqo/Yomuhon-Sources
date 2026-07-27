# Declarative discovery contract (v1 extension)

Yomuhon executes capabilities. `Yomuhon-Sources` defines providers.

This extension adds optional source-owned discovery without provider-specific Swift. Existing source configs remain decodable because `supports.genres` and top-level `discover` are optional.

## Capabilities

```json
"supports": {
  "search": true,
  "popular": true,
  "details": true,
  "chapters": true,
  "pages": true,
  "genres": true,
  "types": true
}
```

`popular` uses `discover.popular` when present. HTML sources may retain legacy `routes.popular` + `selectors.popular` for older app versions.

`genres: true` requires `discover.genres`. The app only displays genres declared by compatible sources.

`types: true` requires `discover.types`. Unlike genres, type IDs are **not** meant to be canonical across sources — the app never merges types from different sources into one global list. Each source declares whatever content-type taxonomy it actually uses (e.g. `manga`/`manhwa`/`manhua`/`novel`), and the per-source catalog screen shows exactly those, isolated to that source. Don't try to reuse another source's type IDs to get cross-source grouping; there isn't any.

## HTML example

```json
"discover": {
  "popular": {
    "route": {
      "path": "/manga/page/{page}",
      "pagination": {"type": "path", "start": 1, "maxPages": 1}
    },
    "selector": {
      "container": "div#book_list div.item",
      "title": {"selectors": ["div.text h3 a"], "attrs": ["text"]},
      "url": {"selectors": ["div.text h3 a"], "attrs": ["href"]},
      "cover": {"selectors": ["img"], "attrs": ["data-src", "src"]}
    }
  },
  "genres": {
    "items": [
      {"id": "action", "title": "Action", "value": "action"}
    ],
    "operation": {
      "route": {
        "path": "/genre/{{genre}}/page/{page}",
        "pagination": {"type": "path", "start": 1, "maxPages": 1}
      },
      "selector": {
        "container": "div#book_list div.item",
        "title": {"selectors": ["div.text h3 a"], "attrs": ["text"]},
        "url": {"selectors": ["div.text h3 a"], "attrs": ["href"]}
      }
    }
  },
  "types": {
    "items": [
      {"id": "novel", "title": "Novela Ligera", "value": "novel"}
    ],
    "operation": {
      "route": {
        "path": "/type/{{type}}/page/{page}",
        "pagination": {"type": "path", "start": 1, "maxPages": 1}
      },
      "selector": {
        "container": "div#book_list div.item",
        "title": {"selectors": ["div.text h3 a"], "attrs": ["text"]},
        "url": {"selectors": ["div.text h3 a"], "attrs": ["href"]}
      }
    }
  }
}
```

`items[].id` is the canonical ID Yomuhon groups across sources **for genres only**. For `types`, `items[].id` just needs to be unique within that source's own list — the app never groups it against another source's ids. `items[].value` is the source-specific slug or ID inserted into `{{genre}}` / `{{type}}`.

## JSON API example

A JSON API source uses the same list mapping shape as `api.search` under `api`:

```json
"discover": {
  "genres": {
    "items": [
      {"id": "action", "title": "Action", "value": "391b0423-d847-456f-aff0-8b0cfc03066b"}
    ],
    "operation": {
      "api": {
        "request": {
          "method": "GET",
          "path": "/manga",
          "query": {"includedTags[]": ["{{genre}}"]}
        },
        "itemsPath": "data",
        "idPath": "id",
        "titlePaths": ["attributes.title.en"]
      }
    }
  },
  "types": {
    "items": [
      {"id": "novel", "title": "Novel", "value": "novel"}
    ],
    "operation": {
      "api": {
        "request": {
          "method": "GET",
          "path": "/manga",
          "query": {"publicationDemographic[]": ["{{type}}"]}
        },
        "itemsPath": "data",
        "idPath": "id",
        "titlePaths": ["attributes.title.en"]
      }
    }
  }
}
```

## Validation

```bash
python3 scripts/validate_sources.py
python3 scripts/validate_sources.py --live --source mangakatana_json
python3 scripts/validate_sources.py --live --source zonatmo_es
```

The live MangaKatana definition now checks search → chapters → pages → first image plus popular and one real genre probe.

`zonatmo_es`'s `discover.types` is unverified as of this writing: `manga`/`manhwa`/`manhua` values are confirmed from the site's own `/library/<value>/...` URL paths, but the `type` query parameter name on `/biblioteca` and the values for `webtoon`/`novela`/`comic`/`one-shot`/`doujinshi`/`oel` are a best-effort guess pending a `--live` run. Re-check before promoting this source out of `testing`.
