# Source Authoring Guide

Este documento define cómo crear una fuente declarativa para Yomuhon.

## Principios

- El JSON contiene datos y selectores; nunca código ejecutable.
- Toda fuente remota debe usar `enabledByDefault: false`.
- Cada host de navegación o imágenes debe figurar en `allowedDomains`.
- Los selectores deben ser compatibles con el motor simple de Yomuhon.
- Una búsqueda válida no basta: la fuente debe entregar capítulos y páginas reales.
- Sitios que exigen login, CAPTCHA fuerte, JavaScript complejo o evasión de protecciones no son candidatos para `declarative-html`.

## Selectores compatibles

El motor admite:

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

No uses pseudoclases, `+`, `~` ni selectores que dependan de ejecución JavaScript.

## Checklist antes de publicar

```text
[ ] index.json incluye la fuente
[ ] source id coincide entre índice, config y test
[ ] versión coincide entre índice y config
[ ] baseURL usa HTTPS
[ ] allowedDomains incluye baseURL y CDN de imágenes
[ ] enabledByDefault = false
[ ] search devuelve mangas, no capítulos
[ ] details conserva una URL canónica del manga
[ ] chapters devuelve enlaces de capítulos reales
[ ] pages devuelve imágenes reales, no logos ni anuncios
[ ] tests/<id>.test.json existe
[ ] python scripts/validate_sources.py pasa
[ ] python scripts/validate_sources.py --live --source <id> pasa
[ ] status = testing hasta probarla dentro de Yomuhon
```

## Estados

- `stable`: probada en el workflow y en la app.
- `testing`: definición disponible para diagnóstico.
- `broken`: falla y el índice impide cargarla.
- `disabled`: retirada temporalmente.
- `deprecated`: reemplazada.

## Activación en la app

`index.enabled: true` solo permite que Yomuhon descubra la definición. No la activa para búsquedas reales. Las fuentes remotas nacen pausadas y el diagnóstico local debe confirmar:

1. búsqueda con resultados;
2. detalle accesible;
3. capítulos no vacíos;
4. páginas no vacías;
5. primera imagen descargable.

Por eso una fuente experimental puede permanecer en `testing` sin poner en riesgo el catálogo principal.
