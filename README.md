# Yomuhon Sources

Repositorio oficial de **definiciones declarativas remotas** para Yomuhon.

**Yomuhon ejecuta capacidades. Este repositorio define proveedores.** La app descarga `index.json`, obtiene cada JSON de fuente y lo ejecuta mediante uno de dos runtimes genéricos:

- `html`: rutas HTTP, selectores CSS simples, regex y extracción declarativa.
- `json-api`: GET, rutas JSON, arrays repetidos y paginación declarativa.

El repositorio no distribuye Swift, JavaScript ni código ejecutable remoto.

## Estado del catálogo

Cada fuente publicada en `index.json` debe tener:

- una definición en `sources/`;
- la **misma versión** en índice y config;
- una definición de regresión en `tests/`;
- dominios coherentes entre índice y config.

Una fuente se publica `stable` únicamente después de pasar Search → Detail → Chapters → Pages → First image. Las fuentes nuevas o en observación permanecen `testing`.

`index.json` es la autoridad de publicación. Una definición `stable` o `testing` con `enabled: true` puede usarse inmediatamente por Yomuhon; el botón de diagnóstico no es una puerta de activación. En schema V1, `enabledByDefault` es un campo legado de compatibilidad que debe permanecer `false` y no controla la activación. Consulta `docs/publication-semantics.md`.

## Añadir una fuente

Requiere Python 3.10 o superior.

```bash
python3 scripts/new_source.py \
  --id mi_fuente \
  --name "Mi Fuente" \
  --language en \
  --engine html \
  --base-url https://example.com
```

JSON API:

```bash
python3 scripts/new_source.py \
  --id mi_api \
  --name "Mi API" \
  --language multi \
  --engine json-api \
  --base-url https://api.example.com
```

El generador crea `sources/<id>.json`, `tests/<id>.test.json` y registra la fuente en `index.json` como `testing`. La plantilla es un esqueleto: debes reemplazar sus rutas, selectores o mappings antes del live validator.

## Validación

```bash
python3 -m pip install -r scripts/requirements.txt
python3 scripts/validate_sources.py
python3 scripts/validate_sources.py --live --source mangapill_json
python3 scripts/validate_sources.py --live --report artifacts/live-source-report.json
```

La validación estática comprueba schema, versión, kind/runtime, rutas, selectores soportados, `allowedDomains` esperados, capacidades Discover y presencia de test por fuente.

La validación live comprueba:

```text
Search
→ manga real
→ capítulos no vacíos
→ páginas no vacías
→ primera imagen descargable
```

Cuando el test declara Discover, también prueba Popular y/o género real.

Las URLs descubiertas en tiempo de ejecución no se bloquean solo por usar un host público que no figure en `allowedDomains`. El live validator emite `LIVE WARN` para ese host y continúa. Sí bloquea destinos no públicos: `localhost`, hosts locales, IP literales privadas, link-local, loopback, multicast/reservadas y cualquier URL que no sea HTTPS.

GitHub Actions ejecuta static en push y pull request. En `main`, ejecución manual y los horarios de las 00:17 y 12:17 UTC también ejecutan live validation y conservan `live-source-report.json` como artifact durante 14 días.

El horario evita el minuto `0`, que GitHub identifica como un periodo de mayor carga para workflows programados.

## Estructura

```text
Yomuhon-Sources/
├─ index.json
├─ sources/
│  ├─ mangadex.json
│  ├─ mangakatana.json
│  ├─ mangapill.json
│  └─ templates/
├─ tests/
│  └─ templates/
├─ schemas/
│  ├─ index-schema-v1.json
│  └─ source-schema-v1.json
├─ scripts/
│  ├─ new_source.py
│  ├─ requirements.txt
│  └─ validate_sources.py
├─ docs/
└─ .github/workflows/validate-sources.yml
```

## Reglas de versionado

Al cambiar selectores, rutas, dominios o mappings:

1. modifica `sources/<id>.json`;
2. aumenta `version` en la config;
3. aumenta la misma versión en `index.json`;
4. actualiza `allowedDomains` en ambos con los hosts **esperados** de la fuente cuando corresponda;
5. ejecuta static + live validation.

Nunca cambies una definición publicada sin aumentar su versión.

## Seguridad

`allowedDomains` documenta los hosts esperados y permite detectar cambios de infraestructura, pero no es una allowlist rígida para CDNs públicos descubiertos durante lectura. La política de ejecución es **HTTPS público solamente**. Yomuhon y el live validator rechazan destinos locales o no enrutable públicamente.

No añadir:

- código remoto ejecutable;
- JavaScript descargable para evaluar dentro de la app;
- Swift dinámico;
- secretos, tokens o cookies privadas;
- bypass de CAPTCHA o protecciones anti-bot.

Consulta `docs/discover-contract.md`, `docs/identity-metadata-contract.md`, `docs/publication-semantics.md` y `docs/source-authoring.md` para el contrato de capacidades y publicación.
