# Yomuhon Sources

Repositorio oficial de configuraciones declarativas para Yomuhon.

## Estructura

```text
Yomuhon-Sources/
├─ index.json
├─ sources/
│  └─ mangakatana.json
└─ schemas/
   └─ source-schema-v1.json
```

## Flujo

1. Yomuhon descarga `index.json`.
2. La app valida `schemaVersion`, `allowedDomains` y `engineMode`.
3. La app descarga cada JSON de `sources/`.
4. Cada fuente debe pasar `Test` antes de considerarse usable.

## V1

La V1 usa un motor declarativo local dentro de la app. El repo remoto será la siguiente etapa.
