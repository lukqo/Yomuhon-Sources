# Publication and runtime health

Yomuhon separates **catalog publication** from **temporary runtime health**.

## Publication authority

`index.json` is the authority for whether a remote source definition is published to the app.

- `enabled: true` makes the entry eligible for discovery.
- `status: stable` or `status: testing` allows the app to load the definition.
- `broken`, `disabled`, and `deprecated` entries are not active reading sources.
- The version in `index.json` and `sources/<id>.json` must match.

A published `stable` or `testing` definition is immediately eligible for Search, Discover, Detail and Reader according to its declared capabilities. A user-facing diagnostic is **not** an activation gate.

## `enabledByDefault` in schema V1

`enabledByDefault` is a legacy compatibility field in source schema V1. It must remain `false` while schema V1 is in use.

It does **not** enable or disable a published source and must not be used by the app as a local activation gate. Publication is controlled by `index.json`.

A future schema revision may remove this legacy field. Until then, authoring tools and the V1 validator keep it as a compatibility sentinel.

## Temporary health

Runtime failures are local observations, not repository publication changes.

Yomuhon may temporarily pause a repeatedly failing source from multi-source Search or Discover through its circuit breaker. A later successful request can recover the source. Known manga routes may still be resolved directly when appropriate so a transient health observation does not destroy an existing reading path.

## Diagnostics

`Test` and smoke diagnostics exist for support, source authoring and maintenance. They verify a real path such as:

```text
Search
→ Detail
→ Chapters
→ Pages
→ First image
```

Diagnostics never have to be pressed by a normal user before reading.
