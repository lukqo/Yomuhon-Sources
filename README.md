# Yomuhon Sources

Repositorio oficial de **definiciones declarativas remotas** para Yomuhon.

Yomuhon contiene el motor. Este repositorio define las fuentes. La app descarga `index.json`, obtiene la definición JSON de cada fuente y la ejecuta mediante uno de dos runtimes genéricos:

- `html`: rutas HTTP + selectores CSS simples.
- `json-api`: requests GET + rutas JSON + paginación declarativa.

El repositorio **no distribuye Swift, JavaScript ni código ejecutable remoto**.

## Añadir una fuente nueva en 5 minutos

Requiere Python 3.10 o superior. Desde la raíz del repo:

```bash
python3 scripts/new_source.py \
  --id mi_fuente \
  --name "Mi Fuente" \
  --language en \
  --engine html \
  --base-url https://example.com
```

Para una API JSON:

```bash
python3 scripts/new_source.py \
  --id mi_api \
  --name "Mi API" \
  --language multi \
  --engine json-api \
  --base-url https://api.example.com
```

El comando crea y registra automáticamente:

```text
sources/<id>.json
tests/<id>.test.json
index.json
```

La fuente nace con:

```text
status = testing
enabled = true
experimental = true
enabledByDefault = false
```

Después:

```bash
python3 -m pip install -r scripts/requirements.txt
python3 scripts/validate_sources.py
python3 scripts/validate_sources.py --live --source mi_fuente
```

La plantilla generada es intencionalmente genérica: **debes editar rutas/selectores o mappings JSON antes de que la prueba real pase**.

## Flujo correcto para publicar

1. Genera el esqueleto con `scripts/new_source.py`.
2. Edita `sources/<id>.json`.
3. Edita `tests/<id>.test.json` con una búsqueda estable.
4. Ejecuta validación estática.
5. Ejecuta la prueba real de esa fuente.
6. Prueba búsqueda → detalle → capítulos → primera página dentro de Yomuhon.
7. Mantén `status: testing` mientras la fuente sea nueva.
8. Sube la `version` y cambia a `stable` solo cuando esté verificada.

## Estructura

```text
Yomuhon-Sources/
├─ index.json
├─ sources/
│  ├─ mangadex.json
│  ├─ mangakatana.json
│  ├─ mangapill.json
│  └─ templates/
│     ├─ html-source.template.json
│     └─ json-api-source.template.json
├─ tests/
│  └─ templates/
│     └─ source.test.template.json
├─ schemas/
│  ├─ index-schema-v1.json
│  └─ source-schema-v1.json
├─ scripts/
│  ├─ new_source.py
│  ├─ requirements.txt
│  └─ validate_sources.py
├─ docs/
│  └─ source-authoring.md
└─ .github/workflows/
   └─ validate-sources.yml
```

## Elegir runtime

### `html`

Úsalo cuando búsqueda, detalle, capítulos y páginas existan en HTML entregado por el servidor.

Buen candidato:

```text
GET /search?q=berserk
→ HTML
→ enlaces de manga
→ página del manga
→ enlaces de capítulos
→ imágenes reales
```

No es buen candidato si exige login, CAPTCHA fuerte, JavaScript complejo o evasión de protecciones.

Selectores soportados por Yomuhon:

```text
tag
.clase
#id
tag.clase
tag[attr]
tag[attr='valor']
tag[attr*='fragmento']
tag:has(.clase)
descendiente descendiente
selector, selector
```

`:has(...)` acepta únicamente **un selector simple descendiente**. No uses otras pseudoclases ni combinadores `>`, `+` o `~`.

### `json-api`

Úsalo cuando el proveedor expone JSON estructurado.

El runtime soporta:

- `GET` declarativo.
- query parameters.
- arrays repetidos, por ejemplo `translatedLanguage[]`.
- templates `{query}`, `{mangaID}`, `{chapterID}`.
- rutas JSON simples como `data`, `attributes.title.en`.
- paginación `offset + limit`.
- `totalPath` opcional.
- protección contra páginas repetidas, IDs duplicados y offsets estancados.

Los `100` de MangaDex son el tamaño del lote, **no un límite de capítulos**.

## Versionar una fuente

Si una web cambia selectores, dominios, rutas o mapping:

1. modifica `sources/<id>.json`;
2. aumenta `version` en el config;
3. aumenta la misma `version` en `index.json`;
4. actualiza `allowedDomains` en ambos si aparece un host nuevo;
5. ejecuta static + live validation.

Nunca cambies una definición publicada sin aumentar su versión.

## Estados

- `stable`: verificada para uso normal.
- `testing`: fuente nueva o en observación.
- `broken`: conocida, pero no debe cargarse.
- `disabled`: retirada temporalmente desde el índice.
- `deprecated`: reemplazada por otra fuente.

`index.enabled: true` permite descubrir la fuente. `enabledByDefault` en una fuente remota debe permanecer siempre en `false`; la app administra disponibilidad y caché localmente.

## Seguridad

Cada host de navegación o imágenes debe existir en `allowedDomains` tanto en el índice como en la configuración. El validador comprueba la coherencia entre ambos.

Nunca añadas:

- código remoto ejecutable;
- JavaScript descargable para evaluar dentro de la app;
- Swift dinámico;
- secretos, tokens o cookies privadas;
- bypass de CAPTCHA o protecciones anti-bot.

## Validación automática

GitHub Actions ejecuta validación estática en pushes y pull requests. En `main`, manualmente y cada 12 horas también ejecuta la prueba real y guarda `artifacts/live-source-report.json` como artifact del workflow.

La prueba real comprueba:

```text
search
→ manga real
→ capítulos no vacíos
→ páginas no vacías
→ primera imagen descargable
```

## Comandos útiles

```bash
# Validar todo sin red
python3 scripts/validate_sources.py

# Probar una sola fuente contra la red
python3 scripts/validate_sources.py --live --source mangapill_json

# Probar varias fuentes concretas
python3 scripts/validate_sources.py --live \
  --source mangadex \
  --source mangapill_json

# Guardar reporte
python3 scripts/validate_sources.py --live \
  --report artifacts/live-source-report.json
```

El contrato completo está en [`docs/source-authoring.md`](docs/source-authoring.md).
