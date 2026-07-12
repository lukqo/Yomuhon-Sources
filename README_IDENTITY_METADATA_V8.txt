Yomuhon-Sources identity metadata contract v8

This patch extends schema v1 with optional provider-declared identity hints:
- HTML list/detail: alternativeTitles, author, year
- JSON API list operations: alternativeTitlePaths, authorPaths, yearPath

The fields are optional and existing source definitions remain valid. No provider-specific runtime code is introduced. See docs/identity-metadata-contract.md.
