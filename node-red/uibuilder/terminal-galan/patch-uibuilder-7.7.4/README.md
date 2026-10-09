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

---

# Parche uibuilder 7.7.4 — validación de URL del editor (falso duplicado)

## Problema que corrige

Al pulsar **Deploy**, el editor avisaba:

```
El espacio de trabajo contiene algunos nodos que no están configurados correctamente:
[MainDisplay] UIB Terminal Galán (reconstruido) <terminal-galan> (uibuilder)
¿Estás seguro de que quieres instanciar?
```

aunque la instancia funcionaba perfectamente. El editor marcaba el nodo uibuilder como
inválido (`valid: false`, `validationErrors: ["url"]`) con:

```json
"urlErrors": { "dup": "Cannot be a URL already in use even if not yet deployed" },
"urlDeployedDup": true, "urlEditorDup": true
```

**Causa raíz:** en `validateUrl()` (editor, `resources/uibuilder.js`) uibuilder traduce
los ids de los nodos que viven dentro de subflows con `fId.split('-')[1]`, porque el
runtime de Node-RED mangla esos ids como `<subflowInstanceId>-<nodeId>`
(`@node-red/runtime/.../Subflow.js`). Ese split se aplicaba **también** a nodos normales
cuyo id contiene guiones: el nuestro es `uib-terminal-galan-v2`, así que
`'uib-terminal-galan-v2'.split('-')[1]` = `'terminal'` ≠ `this.id` → se reportaba como
duplicado. Los ids autogenerados por Node-RED no llevan guiones, por eso el bug de
uibuilder (presente en v7.7.4 y en `master`) solo aparece con ids personalizados.

## El parche

En las dos comprobaciones (instancias *deployed* y *editor*) se aplica el split de
subflow **solo si el id mapeado no es ya el del propio nodo**:

```js
// antes
if ( fId.indexOf('-') !== -1 ) {
    fId = fId.split('-')[1]
}

// después
if ( fId !== this.id && fId.indexOf('-') !== -1 ) {
    fId = fId.split('-')[1]
}
```

Así, para un nodo normal (incluido uno con guiones en el id) `fId === this.id`, no se
trunca y `urlDeployedDup`/`urlEditorDup` quedan en `false`. Para subflows, el id
mangado sí es distinto de `this.id`, por lo que el comportamiento original se conserva.

## Cómo se aplica

Script idempotente incluido (hace backup `.bak-<fecha>` la primera vez):

```bash
# desde docker2/ (o cualquier ruta)
./node-red/uibuilder/terminal-galan/patch-uibuilder-7.7.4/apply-editor-url-dup-fix.sh

# opcional: para recargar el registro del editor
docker compose restart node-red
# y recargar el editor en el navegador con Ctrl+F5
```

Archivo afectado (bind mount `/data` = host `docker2/node-red`):

```
docker2/node-red/node_modules/node-red-contrib-uibuilder/resources/uibuilder.js
```

## Verificación

Con Chrome headless + CDP sobre el editor (`http://localhost:1880/`):

```js
RED.nodes.node('uib-terminal-galan-v2').valid   // antes: false → ahora: true
```

Y un barrido de todos los nodos del flujo no debe reportar ninguno inválido
(`invalidCount: 0`).

## ⚠️ Importante

Como vive en `node_modules` (ignorado por git), el parche **se pierde al reinstalar o
actualizar `node-red-contrib-uibuilder`**. Reaplicarlo con el script de arriba.
