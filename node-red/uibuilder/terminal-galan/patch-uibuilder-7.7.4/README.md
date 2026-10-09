# Parche uibuilder 7.7.4 — bundle de cliente

## Problema que corrige

El HMI de Terminal Galán (`http://<host>:1880/terminal-galan/`) cargaba el SVG la
primera vez, pero **al refrescar (F5) la pantalla dejaba de cargar** (se quedaba en
"Esperando el SVG y los datos de Node-RED...", a veces con la consola mostrando):

```
TypeError: Cannot read properties of undefined (reading 'replace')
    at urlJoin (uibuilder.iife.min.js)
    at Uib.start (uibuilder.iife.min.js)
    at .../terminal-galan/js/main.js:2
```

**Causa raíz:** bug del bundle del cliente `uibuilder.iife.min.js` v7.7.4.

- El constructor lanza un `fetch(location.href, { method: "HEAD" })` para leer las
  cabeceras `uibuilder-*`; hasta que responde, `this.httpHeaders` queda en `{}`.
- Si `uibuilder.start()` se ejecuta **antes** de que ese HEAD termine (caso típico al
  refrescar, porque `main.js` ya está en caché), `start()` entra en la rama
  `if (this.httpHeaders)` y hace `this.set("httpNodeRoot", this.httpHeaders["uibuilder-webroot"])`,
  que es `undefined`.
- Después llama `urlJoin(this.httpNodeRoot, ...)`, que hace `undefined.replace(...)` y
  revienta. La excepción aborta el resto de `main.js`, por lo que `loadSVG()` nunca se
  ejecuta.

Es una condición de carrera: en la primera carga a veces gana el HEAD (funciona) y en
los refrescos suele ganar `main.js` (falla). Reproducido con Chrome headless.

## El parche

En `urlJoin()` se añade un filtro que elimina los argumentos `undefined`/`null` antes
de aplicar `.replace()`:

```js
// antes
.map(function(i){return i.replace(/^\/|\/$/g,"")})

// después
.filter(function(i){return i!==void 0&&i!==null})
.map(function(i){return i.replace(/^\/|\/$/g,"")})
```

Así, aunque `httpNodeRoot` llegue `undefined`, `urlJoin()` produce
`/uibuilder/vendor/socket.io` correctamente y no revienta.

Además, en `www/js/main.js` **se eliminó la llamada manual `uibuilder.start()`**: en
UIBUILDER v7 el cliente se auto-inicia cuando termina el HEAD (evento
`uibuilder:httpHeadersReady`). Ambas medidas juntas eliminan el problema.

## Cómo se aplica (en producción)

Ubicación del archivo real (bind mount `/data` = host `docker2/node-red`):

```
docker2/node-red/node_modules/node-red-contrib-uibuilder/front-end/uibuilder.iife.min.js
```

1. Hacer backup del original.
2. Copiar este bundle parcheado sobre el original.
3. Reiniciar node-red: `docker compose restart node-red` (desde `docker2/`).

Ejemplo:

```bash
UIB=node-red/node_modules/node-red-contrib-uibuilder/front-end/uibuilder.iife.min.js
cp "$UIB" "$UIB.bak-$(date +%Y%m%d_%H%M%S)"
cp node-red/uibuilder/terminal-galan/patch-uibuilder-7.7.4/uibuilder.iife.min.js "$UIB"
docker compose restart node-red
```

## Verificación

Con Chrome headless: carga inicial + varias recargas seguidas, todas con el SVG
inyectado (`#svg1` presente) y sin excepciones de `urlJoin` en consola.

## ⚠️ Importante

Este archivo vive en `node_modules`. **Se pierde si se reinstala o actualiza
`node-red-contrib-uibuilder`** (por ejemplo al reconstruir la imagen o correr
`npm install`). Si eso ocurre, hay que reaplicar el parche con este bundle de
referencia.

Referencia cruzada: el proyecto SCADA usa el mismo parche en
`SCADA/docker/node-red/uibuilder/cromatografia/patch-uibuilder-7.7.4/`.
