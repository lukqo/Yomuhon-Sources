# Identity metadata contract

Yomuhon keeps work identity conservative. A source may optionally provide identity hints; the app still prefers duplicate cards over merging different works.

## HTML selectors

`listSelector` and `detailSelector` may declare:

```json
{
  "alternativeTitles": { "selectors": [".alt-title"], "attrs": ["text"] },
  "author": { "selectors": [".author"], "attrs": ["text"] },
  "year": { "selectors": [".year"], "attrs": ["text"] }
}
```

`alternativeTitles` may be separated by `|`, `;`, or line breaks. `year` extracts a four-digit year in the 1900–2099 range.

## JSON API operations

Search and generic discovery API operations may optionally declare:

```json
{
  "alternativeTitlePaths": ["attributes.altTitles.*.*"],
  "authorPaths": ["relationships.author.attributes.name"],
  "yearPath": "attributes.year"
}
```

Each provider owns its paths in this repository. The app does not contain provider-specific identity rules.

## Merge policy

Identity metadata is evidence, not permission to merge aggressively. Yomuhon rejects a merge when declared years differ by more than one year or when both declared authors conflict. Exact overlap between a primary title and an alternative title is accepted. Fuzzy matching remains intentionally conservative.
