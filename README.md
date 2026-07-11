# Yomuhon Sources

Repositorio oficial de configuraciones declarativas para Yomuhon.

El repositorio contiene datos, rutas y selectores. No descarga ni ejecuta código remoto dentro de la aplicación.

## Estructura

```text
Yomuhon-Sources/
├─ index.json
├─ sources/
│  ├─ mangakatana.json
│  ├─ mangapill.json
│  └─ templates/
│     └─ madara-template.json
├─ schemas/
│  ├─ index-schema-v1.json
│  └─ source-schema-v1.json
├─ tests/
│  ├─ mangakatana.test.json
│  └─ mangapill.test.json
├─ scripts/
│  ├─ requirements.txt
│  └─ validate_sources.py
└─ .github/workflows/
   └─ validate-sources.yml
```

## Contrato de seguridad

1. Yomuhon descarga `index.json` por HTTPS.
2. Solo acepta configuraciones cuyo identificador, versión y dominios coinciden con el índice.
3. Todas las fuentes remotas usan `enabledByDefault: false`.
4. Descubrir una fuente no significa activarla.
5. La app solo la vuelve operativa después de aprobar búsqueda → capítulos → páginas.
6. Los fallos consecutivos la pausan y una comprobación posterior puede recuperarla automáticamente.
7. El caché local mantiene la última configuración válida cuando GitHub no responde.

## Estados

- `stable`: verificada y apta para uso normal.
- `testing`: visible para diagnóstico, pero todavía experimental.
- `broken`: conocida, pero no debe cargarse.
- `disabled`: apagada desde el índice.
- `deprecated`: reemplazada por otra fuente.

## Validación automática

La acción de GitHub ejecuta dos niveles:

- **Validación estática:** JSON, schemas, ids, versiones, dominios, capacidades, rutas, selectores compatibles y archivos de prueba.
- **Prueba real:** consulta el sitio, busca un manga, abre el detalle, obtiene capítulos, extrae páginas y solicita una imagen real.

La prueba real se ejecuta en cada `push` fuera de pull requests, manualmente y mediante cron cada 12 horas.

### Ejecutar localmente

```bash
python3 -m pip install -r scripts/requirements.txt
python3 scripts/validate_sources.py
python3 scripts/validate_sources.py --live
```

Para revisar solo una fuente:

```bash
python3 scripts/validate_sources.py --live --source mangapill_json
```

## Añadir una fuente

1. Crear `sources/<id>.json` con `enabledByDefault: false`.
2. Crear `tests/<id>.test.json`.
3. Añadir la entrada a `index.json` como `status: testing`.
4. Ejecutar la validación estática.
5. Ejecutar la prueba real.
6. Probarla dentro de Yomuhon en Mac, iPhone e iPad.
7. Cambiarla a `stable` solamente después de confirmar búsqueda, detalle, capítulos y lector.

Consulta `docs/source-authoring.md` para el contrato completo.
