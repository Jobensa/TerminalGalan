# Migración HMI a UIBUILDER — Terminal Galán

Este documento registra la migración de la HMI de Terminal Galán desde Node-RED
Dashboard (1 y 2) hacia **UIBUILDER**, siguiendo el estándar del proyecto SCADA.

> Nota: la migración de persistencia a **InfluxDB 2.x** está en
> [`INFLUXDB2_MIGRATION.md`](./INFLUXDB2_MIGRATION.md).

## 1. Arquitectura

- **Node-RED** sirve la HMI en `http://<host>:1880/terminal-galan/`.
  - Correcto: `http://<host>:1880/terminal-galan/`
  - Incorrecto: `http://<host>:1880/uibuilder/terminal-galan/`
- Nodo UIBUILDER: `uib-terminal-galan-v2`
  - `url: terminal-galan`, `sourceFolder: www`, `templateFolder: blank`,
    `copyIndex: false`, `okToGo: true`.
- Carpeta de la instancia: `docker2/node-red/uibuilder/terminal-galan/`
  - `www/index.html` — página maestra.
  - `www/css/style.css` — estilos (incluye popups).
  - `www/js/main.js` — cliente (carga SVG, comandos y popups).
  - `www/svg/main-display.svg` — SVG principal extraído del flow.
  - `patch-uibuilder-7.7.4/` — bundle parcheado de UIBUILDER (ver §3).

## 2. Carga del SVG (dos vistas)

Los SVG ya no están embebidos en plantillas del flow: se extrajeron a archivos y el
cliente los carga con `fetch`:

- `www/svg/main-display.svg` → vista **Principal** (`#view-main`).
- `www/svg/raspador.svg` → vista **Raspador** (`#view-raspador`), 43 KB.

`index.html` define una **barra lateral** colapsable (estándar SCADA) con la
navegación Principal / Raspador, el indicador de conexión y un reloj; además de los
contenedores `#view-main` y `#view-raspador` y el contenedor de notificaciones
`#tg-toasts`. `main.js` alterna la vista activa y los comandos del servidor pueden
acotarse con el campo `view` (`"main"` / `"raspador"`); sin `view` se aplican a
ambas. El acotado evita cruces de ids repetidos entre ambos SVG
(`FIT_2001_FLOW_BACK`, `PB_FIT_2001`, `svg1`, …).

### 2.1. Barra lateral

`#sidebar` reproduce el patrón del proyecto SCADA (`telemetria/www`):

- Colapsada a **60 px** y se expande a **190 px** al pasar el mouse (`.sidebar:hover`);
  el contenido usa `.content { margin-left: 60px }`.
- Botones `.sb-btn` con icono y etiqueta; el botón activo lleva borde y color de acento.
- Zona de estado (punto + texto `#connection-status`) y reloj actualizado por `main.js`.
- La navegación es con `data-view` y la maneja `main.js` (reutiliza `#app-nav`).

Los elementos SVG con interacción reciben la clase **`.tg-clickable`**
(`cursor: pointer`) al enlazarse en `bindButtons`; así todos los botones del SVG,
igual que los de la barra lateral y los popups, muestran el puntero al pasar el mouse.

El cliente `www/js/main.js` es compatible con los comandos que ya emitía el nodo
`ui-svg` del Dashboard: `set_text`, `set_style_attribute` y `add_event` (los
`add_event` del servidor ya no se usan; ver §3.2).

## 3. Corrección crítica: el SVG dejaba de cargar al refrescar (F5)

**Síntoma:** el SVG cargaba la primera vez, pero al refrescar la pantalla quedaba en
"Esperando el SVG y los datos de Node-RED...".

**Causa raíz (bug del bundle cliente `uibuilder.iife.min.js` v7.7.4):**

- El constructor lanza `fetch(location.href, { method: "HEAD" })` para leer las
  cabeceras `uibuilder-*`; hasta que responde, `this.httpHeaders` queda en `{}`.
- Si `uibuilder.start()` se ejecuta antes de que termine el HEAD (caso típico al
  refrescar, porque `main.js` está en caché), `start()` entra en la rama
  `if (this.httpHeaders)` y hace
  `this.set("httpNodeRoot", this.httpHeaders["uibuilder-webroot"])`, que es `undefined`.
- Luego `urlJoin(this.httpNodeRoot, ...)` hace `undefined.replace(...)` y revienta:

  ```
  TypeError: Cannot read properties of undefined (reading 'replace')
      at urlJoin (uibuilder.iife.min.js)
      at Uib.start (uibuilder.iife.min.js)
      at .../terminal-galan/js/main.js:2
  ```

  La excepción aborta el resto de `main.js`, por lo que `loadSVG()` nunca se ejecuta.

Es un *race condition*: a veces gana el HEAD (funciona) y en los refrescos suele ganar
`main.js` (falla). Reproducido con Chrome headless.

**Solución aplicada (2 medidas):**

1. **Parche del bundle** aplicado al archivo instalado:
   `docker2/node-red/node_modules/node-red-contrib-uibuilder/front-end/uibuilder.iife.min.js`.
   En `urlJoin()` se filtran los argumentos `undefined`/`null` antes de `.replace()`.
   El bundle de referencia está en
   `docker2/node-red/uibuilder/terminal-galan/patch-uibuilder-7.7.4/`
   (ver su `README.md`). Es **el mismo parche** que usa SCADA en
   `SCADA/docker/node-red/uibuilder/cromatografia/patch-uibuilder-7.7.4/`.
2. **Eliminar la llamada manual `uibuilder.start()`** de `www/js/main.js`. En UIBUILDER v7
   el cliente se auto-inicia al terminar el HEAD (evento `uibuilder:httpHeadersReady`).

> ⚠️ El parche vive en `node_modules`; se pierde si se reinstala/actualiza
> `node-red-contrib-uibuilder`. Reaplicar el bundle de referencia y reiniciar Node-RED.

**Verificación:** Chrome headless, carga inicial + 6 recargas seguidas → SVG presente
(`#svg1`), estado "Conectado", sin excepciones.

## 3.1. Interactividad de los botones del SVG (disparo de popups)

El SVG tiene 14 zonas con `id` (`PB_LLENAR1`, `PB_CISTERNA1`, `PB_PIT_2001`, …) y tres
más en la vista Raspador (`PIT_2002_HH`, `PIT_2002_H`, `SIC_2002_SP`). Los manejadores
se registran **en el cliente** (`www/js/main.js`, tabla `BUTTONS`) tras cargar cada SVG
por `fetch`; cada botón hace `uibuilder.send({ topic: <id>, payload: <id> })`.

> En la versión anterior los `add_event` los enviaba el servidor desde el nodo
> `Load SVG`. Ese nodo se eliminó junto con la cadena `Plantilla SVG`/`retardo`; el
> registro en cliente es más simple y no depende de mensajes de control de UIBUILDER.

**Verificación (clics reales sobre el SVG):**

- `#PB_CISTERNA1` → popup "Datos de carga" (llenado).
- `#PB_LLENAR1` → popup "Confirmación" y responde `ui_confirm` con `context:'llenar1'`.
- `#PB_CERRAR1` → popup "Confirmación" con `context:'close1'`.
- `#PB_PIT_2001` → popup "Configuración de PIT_2001" y responde `tag_update`.
- `#SIC_2002_SP` (Raspador) → popup "SIC 2002 Setpoint" y actualiza `SIC_2002.SP`.
- `#PIT_2002_HH` / `#PIT_2002_H` (Raspador) → popup y actualizan `PIT_2002.HH` / `.H`.
- Carga inicial + 3 recargas: SVG principal y Raspador presentes y popups funcionando.


## 4. Popups migrados desde Dashboard 2

Implementados en `www/js/main.js` + `www/css/style.css`, disparados por los mismos
topics que usa el flow actual:

| Popup | Topic disparador | Respuesta que envía |
|-------|------------------|---------------------|
| Formulario de llenado | `LLENADO` | `{topic:'OK', payload:{...,origen:'LLENADO'}}` |
| Configuración de alarmas | `open_alarm_config` | `{topic:'tag_update', payload:{...}}` |
| Confirmación genérica | `ui_confirm` | `{topic:'ui_confirm', payload:{result:'ok'\|'cancel', context}}` |
| Edición de setpoint | `ui_setpoint` | `{topic:'ui_setpoint', payload:{tag,value,context}}` |
| Tiquete LPG | `TIQUETE_LPG` | solo muestra el reporte; botón 🖨️ Imprimir |
| Avisos / errores | `ui_notify` | toast transitorio (5 s) |
| Lista/gestión de cisternas | `LISTA_CISTERNAS`, `EDIT_CISTERNA`, `OPEN_POPUP`, `REFRESH_LISTA` | `{topic:'CISTERNA_SELECCIONADA'\|'INSERT'\|'UPDATE'\|'DELETE', payload:{...}}` |

### Confirmaciones con contexto

El popup de confirmación es único (`ui_confirm`). El servidor envía
`{text, context}` y el cliente devuelve `{result:'ok'|'cancel', context}`. El contexto
selecciona la acción:

| `context` | Acción |
|-----------|--------|
| `llenar1` / `llenar2` | `function 12` / `function 16` |
| `pause1` / `pause2` | `SetPause1` / `SetPause2` |
| `close1` / `close2` | `SetClose1` / `SetClose2` |

Los nodos `c232cd5d6109fedb`, `f100d024ae7c59d3`, `9476a829405ca4d6`,
`76e69bd2986067c6`, `3e7dae42210507b1` y `8fa9952dc0738d17` ahora emiten el
`ui_confirm` con su contexto. Las funciones de acción aceptan `cancel` en
minúsculas (respuesta del popup UIBUILDER).

### Enrutamiento (nodo `UIB Router`)

La salida 1 del nodo UIBUILDER (mensajes del cliente) se conecta a:

- **`SelectEvent`** (`89cf21ba1acbaf97`): eventos de los botones del SVG (`PB_*`).
- **`UIB Router`** (`uib-router`, función de 5 salidas): enruta las respuestas de los
  popups:

  | Salida | Destino | Uso |
  |--------|---------|-----|
  | 1 | `e513baa3401879b3` (To FormFill) | Envío del formulario de llenado (`OK`) |
  | 2 | `uib-confirm-prep` → `uib-confirm-switch` | Confirmación por `context` |
  | 3 | `uib-setpoint-prep` → `uib-setpoint-switch` | Setpoint por `context` |
  | 4 | `49958ca9210d0c38` (Prepare Query) | Cisternas (`CISTERNA_SELECCIONADA`/`INSERT`/`UPDATE`/`DELETE`) |
  | 5 | `ea9da6f09b500e72` (preparar query) | Alarmas (`tag_update`) |
- **`50ba8e0e315ffe7f`** (switch del Raspador): `SIC_2002_SP` → setpoint (`context:'sic_sp'`);
  `PIT_2002_HH`/`PIT_2002_H` → `uib-sp-hh`/`uib-sp-h` (`context:'pit_hh'`/`'pit_h'`).

Los avisos de estado/errores que antes salían por `ui-notification` (Dashboard 2) y
`ui_toast` (Dashboard 1) ahora pasan por `uib-notify` → topic `ui_notify` → toast.

## 5. Eliminación de Dashboard 1/2 y de la cadena SVG/templates

Se eliminaron **54 nodos**: los 46 nodos de Dashboard 1/2 (`ui_*`/`ui-*`), la cadena
`inject → delay → Plantilla SVG → Load SVG`, el `delay` y la plantilla del Raspador, y
la función `function 25` de inicialización del Raspador. También se limpiaron los
`wires` que apuntaban a nodos eliminados.

Se eliminaron de `node-red/package.json` y de `node_modules`:

- `node-red-dashboard` (Dashboard 1)
- `@flowfuse/node-red-dashboard` (Dashboard 2)
- `node-red-contrib-ui-svg`
- `@bartbutenaers/node-red-dashboard-2-ui-svg` (nodo `ui-svg`)

La HMI queda **sin dependencia de Dashboard**: los comandos de dibujo
(`set_text`/`set_style_attribute`) los emiten `function 20` (Principal) y `Commands_svg`
(Raspador) hacia UIBUILDER, con el campo `view` para acotar cada SVG.

## 5.1. Tiquete LPG

El nodo `merge-datos` (flujo `flujo-tiquete-lpg`) marca `msg.topic = 'TIQUETE_LPG'` y
envía el reporte a UIBUILDER; el cliente lo renderiza en un popup imprimible
(`buildTiquete` + `printTiquete` en `main.js`, estilos `.tiquete-*` en `style.css`).
Reemplaza a la plantilla Dashboard `09d24cd5ab8f3f33`.

## 5.2. Pantalla Raspador (segunda vista)

- SVG extraído a `www/svg/raspador.svg` (antes plantilla `19e3606adcc6e365`).
- Vista alterna con botón de navegación; sus botones se enlazan en cliente.
- Displays en vivo: `UpdateDisplay` → `Commands_svg` → UIBUILDER (`view:'raspador'`).
- Setpoints `SIC_2002_SP`, `PIT_2002_HH`, `PIT_2002_H` mediante el popup común.
  Los `ui_toast` del Raspador se eliminaron (no propagaban mensajes); ahora HH/H son
  funcionales.

## 6. Cómo verificar / reiniciar

```bash
cd docker2
docker compose restart node-red
# endpoints
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:1880/terminal-galan/
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:1880/terminal-galan/svg/main-display.svg
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:1880/terminal-galan/svg/raspador.svg
```

Prueba de refresco (Chrome headless): cargar `http://localhost:1880/terminal-galan/`,
recargar varias veces y confirmar que `#svg1` sigue presente y la consola sin
`urlJoin`.

## 7. Grafana e InfluxDB 2

Los tableros de Grafana y la escritura a InfluxDB 2 se revisaron y corrigieron:
fuente InfluxDB 2 (Flux) y tablero provistos de forma declarativa, y el payload
del nodo `influxdb out` ajustado al formato de InfluxDB 2. El detalle está en
[`INFLUXDB2_MIGRATION.md`](./INFLUXDB2_MIGRATION.md).

## 8. Pendiente

- Validación en campo de la HMI UIBUILDER (botones, confirmaciones, tiquete,
  setpoints y cambio de vista) sobre el equipo final.
