# Terminal Galán — Estado del Proyecto (handoff)

> **Para continuar en una sesión nueva**: leer este documento y
> `modbus-gateway/README.md`. Si se retoma el trabajo, empezar por la sección
> "Pendientes" y "Cómo continuar".
> Actualizado: 2026-10-09.

## 1. Qué es

HMI de planta (gas butano/propano, cisternas, batch y reportes) con:

- **UI**: Node-RED + **UIBUILDER** (migrado desde Dashboard 2).
- **Datos históricos**: **InfluxDB 2.7** + **Grafana** (dashboards aprovisionados).
- **PLC/Modbus**: el V560 (compresor/coriolis) se lee por serial RTU
  (`/dev/ttyUSB0`, 57600) y se escribe SP/CV/alarmas. Antes se leía con nodos
  Modbus de Node-RED; **ahora un gateway Rust (Modbus → MQTT)** hace lecturas y
  escrituras, y Node-RED solo usa MQTT (mosquitto).

## 2. Repositorio

- Ruta local del repo git: `TerminalGalan/docker2` (`.git` aquí, NO en la raíz).
- Remoto: `git@github.com:Jobensa/TerminalGalan.git`, rama `main`.
- HEAD local + remoto: `731fb6c` ("Migración a UIBUILDER + InfluxDB 2.7; repo basado en docker2").
- ⚠️ **Historial reescrito** (purga de secretos con `git filter-branch`, force-push).
  Cualquier clon/copia vieja debe `git fetch --all && git reset --hard origin/main`
  o re-clonar. `.git` ≈ 580 KB, árbol ≈ 63+ archivos.
- Fuera de git (no versionar): `docker/` (stack viejo Dashboard2), `Python/`,
  `docs/`, `PLC/`, `FC/`, `FlowVapores/`.

## 3. Stack Docker (`docker2/compose.yaml`)

| Servicio | Imagen | Notas |
|---|---|---|
| `influxdb2` | influxdb:2.7 | host network, datos en ./influxdb-data |
| `grafana` | grafana/grafana | provisioned datasource+dashboards |
| `mosquitto` | eclipse-mosquitto | broker localhost:1883, allow_anonymous (dev) |
| `node-red` | nodered/node-red | ./node-red:/data |
| `modbus-gateway` | terminalgalan-modbus-gateway (build local) | **nuevo**: Rust Modbus→MQTT |

**Regla**: siempre `docker compose up -d <servicio>` (nunca `up -d` sin lista).
Estado actual: influxdb2, grafana, mosquitto, node-red corriendo.

## 4. Migraciones completadas

1. **UIBUILDER** — ver `UIBUILDER_MIGRATION.md` (HMI nueva en `node-red/uibuilder/`).
2. **InfluxDB 2.7 + Grafana** — ver `INFLUXDB2_MIGRATION.md`. Datasource sano,
   4 buckets; dashboards Grafana provisionados.
3. **Purga de historial git** — se eliminaron del histórico: tokenID.txt,
   flows_cred.json, grafana.db, node_modules, .npm, tiquetes_pdf, backups, *.db.
   Force-push a main (`731fb6c`). Respaldo: `/tmp/opencode/TerminalGalan-pre-purge.bundle`.
4. **Rotación token InfluxDB** — token nuevo all-access "TerminalGalan SCADA"
   (id `11743625d1f58000`) en `docker2/.env`; Node-RED re-cifrado en
   `flows_cred.json` (algoritmo Node-RED: aes-256-ctr, key=sha256(`_credentialSecret`),
   ver `/tmp/opencode/rotate-cred.js`). Auth viejo eliminado (token viejo → 401).
5. **Gateway Modbus Rust (nuevo)** — ver sección 5.

## 5. Gateway Modbus RTU/TCP → MQTT (`docker2/modbus-gateway/`)

Rust (patrón copiado del gateway ABB del SCADA: `pac_to_mqtt_rust`, bin
`abb-modbus-to-mqtt`) con transporte **RTU serial y TCP** y **escrituras** (FC 6
registros y FC 5 coils). Ver `modbus-gateway/README.md`.

- **Tópicos**:
  - Lecturas por etiqueta: `plant/read/<TAG>` (payload `{tag,value,timestamp}`)
  - Bloque crudo: `planta_modbus/<device>/<block>` (payload `{registers:[...],...}`)
  - Escrituras (suscrip.): `plant/write/<TAG>` (payload número, o true para coil)
  - Estado: `planta_gateway/...` (retain)
- **Config**: `config/terminal-galan.dev.json` (simulador TCP 127.0.0.1:5502)
  y `config/terminal-galan.prod.json` (serial /dev/ttyUSB0 57600 — **completar
  mapa del compresor, ver PENDIENTES**).
- **Probado end-to-end en dev** (2026-10-09):
  - Lectura: Sim Modbus TCP → gateway → `planta_modbus/v560_sim/coriolis`
    (1 msg/seg, registros 100..124) → Node-RED `mqtt in` → `ExtractRegisters` →
    `function 2` → globales → InfluxDB (`analogas7.pit_2001` = 348.9 ✓).
  - Escritura: `plant/write/STATUS_CISTERNA=2` → reg 115 → sim arrancó batch
    (`🟢 ACTIVO - Tiquete: 1` ✓); `plant/write/SIC_SP=765` → reg 76 ✓ (log).
- **Dockerfile** multi-stage (rust:1-slim-bookworm → debian:bookworm-slim);
  puerto serie mapeado en compose (`devices: /dev/ttyUSB0:/dev/ttyUSB0`).
  Compila con `cargo` local 1.97 sin libudev (serial por libc/termios).

## 6. Flujo Node-RED (cambios modbus → MQTT)

En `node-red/flows.json` (id de nodos nuevos `aa000000000000xx`):

- Se **eliminaron** los nodos: `modbus-client` (3, V560/ModbusSIM/SIM_MBTCP),
  `modbus-read` (ReadPLC), `modbus-write` (6: SendHH/H/PressureIN/SIC_CV/SIC_SP×2)
  y `modbus-flex-write` (Force coils).
- `package.json`: quitado `node-red-contrib-modbus`.
- **Nuevos**:
  - `mqtt in` `plant/read/#` → "Get PLC Data" (antes plant/#; separado de
    `plant/write` para evitar auto-suscripción de las escrituras).
  - `mqtt in` `planta_modbus/#` → `ExtractRegisters` (payload.registers → array)
    → `function 2`.
  - `mqtt out` `plant/write` (topic dinámico desde msg.topic) para las 6
    escrituras; 6 `change` nodes fijan msg.topic (`plant/write/{HH,H,PRESSURE_IN,SIC_CV,SIC_SP,STATUS_CISTERNA}`).
  - `function 4`: coils emiten `msg.topic=plant/write/{START,STOP,CLEAR}_BATCH`
    y payload `true`.
  - `inject` once → `InitGlobals`: inicializa `PIT_2001`, `TIT_2001`, `FIT_2001`,
    `DIT_2001`, `UIT_2001_DENSITY`, `UIT_2001/2002/2003`, `PIT_2002`, `SIC_2002`,
    `PROMEDIOS`, `SEL_CISTERNA`, `STATUS_CISTERNA{1,2}`, `SEGMENT_VALUES{1,2}`
    (evita errores de undefined con datos reales).
- `function 48` (historial alarmas): guardas para `msg.alarms`/`TagName`
  (errores "Invalid context key" preexistentes, ahora visibles con datos).

## 7. Pendientes

1. **Mapa de registros del compresor (producción)**: completar bloque `compresor`
   en `config/terminal-galan.prod.json` (etiquetas `UIT_2002_SPEED/TEMPERATURE/
   PRESSURE_IN/PRESSURE_OUT/FLOW/SP/CV/HH/H` y `PIT_2002_PV`) con las direcciones
   reales del V560 y poner `"enabled": true` + `"publish_registers_only": false`.
2. **Despliegue en producción** (Windows Server + Debian + Docker):
   - `git pull` / clonar en la máquina de producción.
   - `docker compose up -d influxdb2 grafana mosquitto node-red modbus-gateway`
     (revisar que `/dev/ttyUSB0` exista y permisos; el servicio monta el device).
   - **Reemplaza el gateway físico RTU→TCP**: el Rust lee el serial RTU directo
     y publica MQTT; Node-RED ya no usa nodos Modbus.
   - Copiar `.env` con el token de InfluxDB (no está en git).
3. **Acciones manuales del usuario**:
   - **Telegram**: revocar/rotar el token en @BotFather (estuvo público en el
     historial viejo hasta el purge). Manual desde la app.
   - mosquitto debe estar arriba para que el gateway y Node-RED se conecten
     (`docker compose up -d mosquitto`).

## 8. Cómo continuar en una sesión nueva

1. Nueva sesión → apuntar al working dir `TerminalGalan/docker2` y leer
   `ESTADO_PROYECTO.md` + `modbus-gateway/README.md`.
2. Tareas típicas: completar mapa del compresor (PENDIENTE 1), adaptar tópicos
   del dashboard si cambian nombres de etiquetas, desplegar (PENDIENTE 2).
3. Referencia rápida de comandos:
   - Build gateway: `cd modbus-gateway && cargo build --release`
   - Dev con simulador: `Python/modbus_tcp/env/bin/python Python/modbus_tcp/modbus_simulator.py`
     + `./modbus-gateway/target/release/modbus-gateway modbus-gateway/config/terminal-galan.dev.json`
   - Ver/inyectar MQTT: `docker exec mosquitto mosquitto_sub -t '#' ` /
     `docker exec mosquitto mosquitto_pub -t 'plant/write/SIC_SP' -m '765'`
   - Reiniciar Node-RED: `docker restart docker2-node-red-1`