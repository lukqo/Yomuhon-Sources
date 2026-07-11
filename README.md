# Yomuhon Sources

Repositorio oficial de configuraciones declarativas para Yomuhon.

## Estructura

```text
Yomuhon-Sources/
├─ index.json
├─ sources/
│  ├─ mangakatana.json
│  └─ templates/
│     └─ madara-template.json
├─ schemas/
│  └─ source-schema-v1.json
├─ tests/
│  └─ mangakatana.test.json
└─ .github/workflows/
   └─ validate-sources.yml
```

## Estados recomendados

- `stable`: usable.
- `testing`: experimental, necesita revisar.
- `broken`: existe, pero no se debe activar.
- `disabled`: apagada desde el índice.
- `deprecated`: reemplazada por otra fuente.

## Flujo

1. Yomuhon descarga `index.json`.
2. Lee configs con `enabled: true`.
3. Valida schema, engine mode y allowed domains.
4. Cachea configs válidas.
5. La app actualiza el catálogo y comprueba salud automáticamente cada 12 horas.
6. Una fuente se pausa solo después de fallos consecutivos y se reactiva sola al recuperarse.
7. El botón **Diagnosticar todas** queda como herramienta manual de depuración, no como requisito para leer.

## Nota

El repo contiene datos y selectores, no código ejecutable remoto.


## Docs

- `docs/source-authoring.md`: cómo crear una fuente.
- `docs/troubleshooting.md`: errores típicos y cómo arreglarlos.
