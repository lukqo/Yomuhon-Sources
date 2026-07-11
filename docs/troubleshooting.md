# Troubleshooting Sources

## La acción falla antes de conectarse al sitio

Ejecuta:

```bash
python3 scripts/validate_sources.py
```

Los errores más comunes son ids o versiones distintos entre `index.json` y `sources/*.json`, dominios ausentes, capacidades sin ruta/selector o sintaxis CSS no soportada.

## Search devuelve `[Cover]`

La búsqueda está tomando el texto alternativo de una portada. Prefiere un contenedor de resultado completo o deja que el título se reconstruya desde la URL. También puedes retirar marcadores mediante `cleanup.removeText`.

## Search devuelve capítulos como mangas

Haz más específico el `container`. La URL canónica del manga debe terminar en algo como:

```text
/manga/title.123
```

y no en:

```text
/manga/title.123/c1
/chapters/123/title-chapter-1
```

## No hay capítulos

Comprueba que los enlaces estén en el HTML inicial. Una lista renderizada exclusivamente con JavaScript no funciona con el motor declarativo actual.

## No hay páginas

Revisa lazy loading y `srcset`. Usa más de un atributo cuando sea necesario:

```json
"attrs": ["data-src", "data-original", "data-lazy-src", "srcset", "src"]
```

Agrega el CDN a `allowedDomains` y bloquea logos, banners, avatares y anuncios mediante `filters.blockContains`.

## La imagen existe, pero el workflow no puede abrirla

Algunos CDN exigen `Referer` o un `User-Agent`. Decláralos en `network.headers`. No intentes saltar CAPTCHA ni protecciones anti-bot.

## El sitio funciona en navegador, pero falla en GitHub Actions

Puede estar bloqueando rangos de IP de centros de datos. Mantén la fuente en `testing` o `broken`; no la marques como `stable` basándote únicamente en una prueba local.

## Cloudflare o CAPTCHA

No intentes evasión. Usa un adaptador nativo controlado o marca la fuente como `broken`.
