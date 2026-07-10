# Troubleshooting Sources

## Search devuelve `[Cover]`

El selector de `title` está tomando texto de una imagen. Revisa:

```json
"title": {
  "selectors": [".title a", "h3 a", "a"],
  "attrs": ["text", "title"]
}
```

Evita contenedores demasiado amplios como `a[href*='/manga/']` si la web tiene links a capítulos mezclados.

## Search devuelve capítulos como mangas

Ajusta el selector de contenedor o usa canonicalización desde URL. El ideal es que el resultado sea:

```text
/manga/title.123
```

no:

```text
/manga/title.123/c1
```

## No hay portada

Agrega más attrs:

```json
"attrs": ["data-src", "data-original", "data-lazy-src", "src", "content"]
```

## No hay páginas

Revisa si la web usa lazy loading, srcset, scripts o CDN diferente. Agrega dominios de imágenes a `allowedDomains`.

## Cloudflare / CAPTCHA

No intentes bypass. Marca fuente como `broken` o usa un adapter nativo controlado.
