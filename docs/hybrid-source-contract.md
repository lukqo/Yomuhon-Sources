# Hybrid source contract

Schema v1 remains backwards-compatible. `engineMode` is the default runtime, while `operationModes` may override `popular`, `search`, `details`, `chapters`, `pages` or `genres`. API requests may declare a separate HTTPS `baseURL`; chapter APIs may derive variables from `mangaURL`/`mangaID` and expose `urlPath`; `identity.preserveQueryItems` preserves only stable public query identifiers. No remote executable code is allowed.
