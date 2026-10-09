# Gateway Modbus RTU/TCP → MQTT (Rust) — Terminal Galán

Servicio Docker en Rust que reemplaza los nodos Modbus de Node-RED
(`node-red-contrib-modbus`) por un gateway a MQTT (mosquitto), igual que el
gateway ABB del SCADA (`pac_to_mqtt_rust`), al que se le añadieron
**escrituras** y **transporte RTU serial** (además de TCP para el simulador).

## Arquitectura

```
V560 (RTU serial /dev/ttyUSB0) ──┐
                                 ├─► modbus-gateway (Rust) ──► mosquitto ──► Node-RED (uibuilder, influxdb)
Simulador Modbus TCP (dev)   ────┘        ▲                                 │
                                          └── plant/write/<TAG> (SP, CV, ...) ◄┘
```

## Tópicos

| Dirección | Tópico | Payload |
|---|---|---|
| Lectura por etiqueta | `plant/read/<TAG>` | `{"tag":"...","value":...,"timestamp":...}` |
| Bloque crudo de registros | `planta_modbus/<device>/<block>` | `{"registers":[...], "address":..., "timestamp":...}` |
| Escritura (suscripción) | `plant/write/<TAG>` | número (registro) o `true`/`1` (coil) |
| Estado dispositivo (retain) | `planta_gateway/devices/<device>/status` | `{"connected":true/false,...}` |
| Estado gateway (retain) | `planta_gateway/status` | `{"mqtt_connected":..., "timestamp":...}` |

Node-RED:
- `mqtt in` → `plant/read/#` → "Get PLC Data" (etiquetas `UIT_2002_*`, `PIT_2002_PV`…).
- `mqtt in` → `planta_modbus/#` → "ExtractRegisters" → "function 2" (bloque crudo de la cisterna/coriolis).
- `mqtt out` → `plant/write/<TAG>` para las escrituras (en vez de `modbus-write`).

## Configuración

- `config/terminal-galan.dev.json` → contra el simulador TCP (`Python/modbus_tcp/modbus_simulator.py`, puerto 5502).
- `config/terminal-galan.prod.json` → RTU serial `/dev/ttyUSB0` 57600 (V560).

Campos de un `Field`: `tag`, `register_offset` (índice dentro del bloque leído),
`scale` y `offset`; el valor publicado es `raw * scale + offset`.

### Mapa de registros (deducido del flujo Node-RED y del simulador)

**Bloque coriolis (regs 100+):**
| Reg (offset) | Etiqueta | Escala | Nota |
|---|---|---|---|
| 100 (0) | `PIT_2001_PV` | /10 | presión, bar |
| 101 (1) | `TIT_2001_PV` | /10 | temperatura, °C |
| 109 (9) | `DIT_2001_PV` | /10 | densidad, kg/m³ |
| 111 (11) | `UIT_2001_TOTAL` | 1 | total, L (palabra baja) |
| 112 (12) | `UIT_2001_FLOW` | /10 | flujo |
| 113 (13) | `UIT_2003_TOTAL` | /10 | |
| 114 (14) | `UIT_2003_FLOW` | /10 | |

**Escrituras (V560):** `SIC_SP`→76, `SIC_CV`→75, `PRESSURE_IN`→73, `HH`→79, `H`→80.
Dev: `STATUS_CISTERNA`→115 (simula el comando de batch), coils `START/STOP/CLEAR_BATCH`→0/1/2.

> **PENDIENTE en producción:** el bloque `compresor` (`UIT_2002_*` y `PIT_2002_PV`)
> está deshabilitado (`"enabled": false`) porque el mapa real de registros del V560
> aún no está confirmado. Cuando se tenga, completar `register_offset`/`scale` de
> cada etiqueta y poner `"enabled": true` y `"publish_registers_only": false`.
> Con `publish_registers_only: true` el gateway sólo publica el bloque crudo
> (`planta_modbus/...`) y Node-RED sigue funcionando con `function 2`.

## Compilar / probar en desarrollo (host)

```bash
cd docker2/modbus-gateway
cargo build --release

# Simulador (puerto 5502):
/media/jose/.../TerminalGalan/Python/modbus_tcp/env/bin/python \
    ../..//Python/modbus_tcp/modbus_simulator.py &
# (ajusta la ruta del venv)

./target/release/modbus-gateway config/terminal-galan.dev.json
# en otra terminal:
docker exec mosquitto mosquitto_sub -t 'planta_modbus/#' -C 2
docker exec mosquitto mosquitto_pub -t 'plant/write/SIC_SP' -m '765'
```

## Docker

Servicio en `compose.yaml` (`modbus-gateway`). En producción habilitar el puerto
serie (`devices: - /dev/ttyUSB0:/dev/ttyUSB0`, ya declarado) y montar el config
como `terminal-galan.json` (ver `command`). No iniciarlo en desarrollo (no hay
`/dev/ttyUSB0`): se prueba con el binario en el host contra el simulador TCP.