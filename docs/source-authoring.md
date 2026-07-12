# Source Authoring Guide

Este documento define el contrato de autoría de fuentes para Yomuhon.

## 1. Regla principal

Una fuente es **datos declarativos**, no un plugin de código.

```text
GitHub source definition
        ↓
DeclarativeSourceRuntime
        ↓
html o json-api
        ↓
Manga / Chapter / Page
```

La aplicación no debe conocer nombres concretos como MangaPill o MangaDex.

## 2. Archivos obligatorios

Cada fuente publicada necesita tres piezas:

```text
index.json                         entrada de descubrimiento
sources/<nombre>.json              definición del runtime
tests/<nombre>.test.json           prueba real reproducible
```

`id`, `name`, `version` y `language` deben coincidir entre el índice y la configuración. `sourceID` del test debe coincidir con `id`.

## 3. Crear el esqueleto

```bash
python3 scripts/new_source.py \
  --id example \
  --name "Example" \
  --language en \
  --engine html \
  --base-url https://example.com
```

Opciones:

```text
--id          [a-z0-9_-], único
--name        nombre visible
--language    en, es, multi, etc.
--engine      html | json-api
--base-url    HTTPS
--domain      host adicional; repetible
```

Ejemplo con CDN:

```bash
python3 scripts/new_source.py \
  --id example \
  --name "Example" \
  --language en \
  --engine html \
  --base-url https://example.com \
  --domain cdn.example.com \
  --domain images.example.net
```

## 4. Campos comunes

```json
{
  "schemaVersion": 1,
  "id": "example",
  "name": "Example",
  "version": 1,
  "language": "en",
  "baseURL": "https://example.com",
  "engineMode": "html",
  "enabledByDefault": false,
  "experimental": true,
  "allowedDomains": ["example.com"],
  "supports": {
    "search": true,
    "popular": false,
    "details": true,
    "chapters": true,
    "pages": true
  }
}
```

### `version`

Empieza en `1`. Auméntala cuando cambie cualquier comportamiento que la app deba volver a descargar: selectores, rutas, mappings, dominios o headers.

### `language`

Código corto (`en`, `es`) o `multi` para una fuente multilenguaje.

### `allowedDomains`

Incluye todos los hosts de documentos y de imágenes. Subdominios de un host permitido son aceptados, pero un dominio diferente debe declararse explícitamente.

### `enabledByDefault`

Siempre `false` para definiciones remotas.

## 5. Fuentes HTML

### Búsqueda

```json
"routes": {
  "search": {
    "path": "/search",
    "query": {
      "q": "{{query}}"
    }
  }
}
```

```json
"selectors": {
  "search": {
    "container": "a[href*='/manga/']",
    "title": {
      "attrs": ["title", "text"]
    },
    "url": {
      "attrs": ["href"],
      "required": true
    },
    "cover": {
      "selectors": ["img"],
      "attrs": ["data-src", "src"]
    }
  }
}
```

El `container` debe representar **mangas**, no enlaces de capítulos.

### Detalle

```json
"details": {
  "title": {
    "selectors": ["h1", "meta[property='og:title']"],
    "attrs": ["text", "content"]
  },
  "synopsis": {
    "selectors": ["meta[name='description']"],
    "attrs": ["content"]
  },
  "cover": {
    "selectors": ["meta[property='og:image']"],
    "attrs": ["content"]
  }
}
```

### Capítulos

```json
"chapters": {
  "container": "a[href*='/chapter/']",
  "title": {
    "attrs": ["text", "title"]
  },
  "url": {
    "attrs": ["href"],
    "required": true
  },
  "number": {
    "from": "url",
    "regex": "chapter-([0-9]+(?:\\.[0-9]+)?)"
  },
  "sort": "numberAscending"
}
```

### Páginas

```json
"pages": {
  "extractors": [
    {
      "type": "css",
      "selector": "picture img, img.page",
      "attrs": ["data-src", "data-original", "srcset", "src"]
    }
  ],
  "filters": {
    "mustContain": [".jpg", ".jpeg", ".png", ".webp"],
    "blockContains": ["logo", "avatar", "banner", "ads/", "icon"]
  }
}
```

Usa regex de páginas solo cuando la URL de imagen exista en el HTML pero no en un nodo seleccionable.

### CSS soportado

```text
tag
.clase
#id
tag.clase
tag[attr]
tag[attr='valor']
tag[attr*='fragmento']
descendiente descendiente
selector, selector
```

No uses:

```text
:first-child
:nth-child(...)
+
~
```

## 6. Fuentes JSON API

La configuración usa `api.search`, `api.chapters` y `api.pages`.

### Search

```json
"search": {
  "request": {
    "method": "GET",
    "path": "/manga",
    "query": {
      "title": "{{query}}",
      "limit": 20
    }
  },
  "itemsPath": "data",
  "idPath": "id",
  "titlePaths": [
    "attributes.title.en",
    "attributes.title.es"
  ],
  "synopsisPaths": [
    "attributes.description.en"
  ]
}
```

`titlePaths` se evalúa en orden y usa el primer string no vacío.

### Chapters

```json
"chapters": {
  "request": {
    "method": "GET",
    "path": "/manga/{mangaID}/feed",
    "query": {
      "translatedLanguage[]": "{{languages}}"
    }
  },
  "pagination": {
    "offsetParam": "offset",
    "limitParam": "limit",
    "limit": 100,
    "maxItems": 10000,
    "totalPath": "total"
  },
  "itemsPath": "data",
  "idPath": "id",
  "numberPath": "attributes.chapter",
  "titlePath": "attributes.title",
  "languagePath": "attributes.translatedLanguage",
  "sort": "numberAscending"
}
```

La paginación termina por respuesta vacía, página corta, total alcanzado, página repetida, ausencia de IDs nuevos u offset no progresivo. `maxItems` es un fusible defensivo.

### Pages

```json
"pages": {
  "request": {
    "method": "GET",
    "path": "/reader/{chapterID}",
    "query": {}
  },
  "baseURLPath": "baseUrl",
  "hashPath": "chapter.hash",
  "itemsPath": "chapter.data",
  "urlTemplate": "{baseURL}/data/{hash}/{item}"
}
```

## 7. Test de una fuente

```json
{
  "sourceID": "example",
  "queries": ["berserk"],
  "probe": {
    "query": "berserk",
    "expectedTitleContains": "Berserk",
    "mangaPathContains": "/manga/",
    "chapterPathContains": "/chapter/"
  },
  "expected": {
    "minSearchResults": 1,
    "minChapters": 1,
    "minPages": 1
  }
}
```

Elige una obra conocida y razonablemente estable. No uses una búsqueda demasiado genérica como `manga` o `action`.

## 8. Checklist

```text
[ ] ID único y válido
[ ] index.json contiene la fuente
[ ] id/name/version/language coinciden
[ ] baseURL usa HTTPS
[ ] allowedDomains incluye navegación y CDN
[ ] enabledByDefault = false
[ ] status = testing
[ ] search devuelve mangas reales
[ ] detail conserva metadata real
[ ] chapters no está vacío
[ ] pages no está vacío
[ ] primera imagen responde como imagen
[ ] test file existe
[ ] validate_sources.py pasa
[ ] --live --source <id> pasa
[ ] probado dentro de Yomuhon
```

## 9. Fallos comunes

### `Blocked image host`

La página usa un CDN no declarado. Añádelo a `allowedDomains` en `index.json` y `sources/<id>.json`, sube `version` y vuelve a validar.

### `Search returned too few results`

Revisa ruta, query parameter y `selectors.search.container` o `api.search.itemsPath`.

### `Details returned too few chapters`

Abre la página del manga y comprueba que los enlaces estén en el HTML entregado por el servidor. Si aparecen solo después de ejecutar JavaScript, esa web no es compatible con el runtime HTML actual.

### `Reader returned too few pages`

Revisa lazy-loading (`data-src`, `data-original`, `srcset`) y hosts CDN.

### La fuente funciona pero Yomuhon sigue usando config vieja

Aumenta `version` en config e índice. El catálogo remoto se versiona por `id + version`.
