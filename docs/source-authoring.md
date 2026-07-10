# Source Authoring Guide

Este documento define cómo crear una fuente declarativa para Yomuhon.

## Principios

- El JSON contiene datos y selectores, no código ejecutable.
- Cada fuente debe declarar `allowedDomains`.
- Cada selector debe tener fallback razonable.
- Si una web necesita login, captcha fuerte o JS complejo, no es buena candidata para `declarative-html`.

## Checklist antes de subir una fuente

```text
[ ] index.json incluye la fuente
[ ] source id coincide entre index.json y sources/*.json
[ ] allowedDomains incluye baseURL host y hosts de imágenes
[ ] search devuelve mangas, no capítulos
[ ] details devuelve título/sinopsis/cover si existen
[ ] chapters devuelve capítulos reales
[ ] pages devuelve imágenes reales, no logos/banners
[ ] tests/*.test.json actualizado
[ ] status = testing hasta probar en Yomuhon
```

## Estados

- `stable`: probada y usable.
- `testing`: experimental.
- `broken`: existe pero falla.
- `disabled`: no debe cargarse.
- `deprecated`: reemplazada.

## Naming

Usa ids explícitos:

```text
mangakatana_json
mangapill_json
example_madara
```

Evita ids genéricos como:

```text
source1
reader
manga
```

## Debug con Source Inspector

En Yomuhon:

```text
Settings → Sources → Inspector
```

Revisa:

- origen bundled/remoto;
- estado del cache;
- último test;
- familia;
- lector/catálogo;
- idiomas;
- URL del índice remoto.
