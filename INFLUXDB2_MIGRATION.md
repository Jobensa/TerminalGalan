# Migración a InfluxDB 2 y Grafana

## Configuración estándar

- Imagen: `influxdb:2.7`
- Servicio / contenedor: `influxdb2`
- URL: `http://localhost:8086`
- Organización: `Petrosantander`
- Bucket: `TGalanDB`
- Token: en `docker2/.env` (`INFLUXDB_INIT_ADMIN_TOKEN`).
- Datos: `docker2/influxdb-data/`

La instancia anterior (InfluxDB 3 / Flight SQL) y el servicio Explorer fueron
retirados del `compose.yaml`.

## Variables de entorno (`.env`)

Siguiendo el estándar del proyecto SCADA, `compose.yaml` toma los valores de
`docker2/.env`:

```
INFLUXDB_INIT_USERNAME=admin
INFLUXDB_INIT_PASSWORD=influxdb
INFLUXDB_INIT_ORG=Petrosantander
INFLUXDB_INIT_BUCKET=TGalanDB
INFLUXDB_INIT_ADMIN_TOKEN=...
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
```

> El token de ejemplo es para la instalación local. Debe cambiarse antes de
> exponer el servicio fuera del equipo.

## Node-RED

- Configuración `influxdb` versión `2.0` (nodo `InfluxDB 2 Local`).
- Nodo de escritura `influxdb out` (`Pruebas`), org `Petrosantander`, bucket
  `TGalanDB`, `precisionV18FluxV20 = ms`.

**Formato del mensaje (corregido):** para `node-red-contrib-influxdb@0.7.0` con
InfluxDB 2 el `msg.payload` debe ser el objeto de **campos**, o un arreglo
`[fields, tags]`. No se usa el formato de InfluxDB 1
(`{fields, tags, timestamp}`), que provocaba que sólo se escribiera el campo
`timestamp`.

La función `function 26` (flujo de telemetría, cada 1 s) emite:

```js
msg.measurement = "analogas7";
msg.payload = [
    {
        pit_2001: pit_2001.PV ?? 0,
        tit_2001: tit_2001.PV ?? 0,
        dit_2001: dit_2001.PV ?? 0,
        time: Date.now()            // fija el timestamp del punto (ms)
    },
    { ubicacion: "separador" }      // tags
];
return msg;
```

Esto escribe la medición `analogas7` con los campos `pit_2001`, `tit_2001`,
`dit_2001` y el tag `ubicacion=separador`.

## Grafana

Se incorporó **Grafana provisioning** (sin configurar a mano la base):

- `grafana-provisioning/datasources/influxdb.yaml`
  - Fuente `InfluxDB` (uid `influxdb`), tipo `influxdb`, versión **Flux**,
    org `Petrosantander`, `defaultBucket: TGalanDB`, token desde
    `${INFLUXDB_INIT_ADMIN_TOKEN}`.
  - `deleteDatasources` elimina la fuente obsoleta de InfluxDB 3
    (`influxdata-flightsql-datasource`).
- `grafana-provisioning/dashboards/scada.yaml` → provider que carga
  `/var/lib/grafana/dashboards`.
- `grafana-dashboards/TerminalGalan/analogas7.json` → tablero
  *Terminal Galán - Analogas* (uid `tgalan-analogas`), panel de series de
  tiempo con consulta Flux sobre `analogas7`.

`compose.yaml` monta `./grafana-provisioning/datasources`,
`./grafana-provisioning/dashboards` y `./grafana-dashboards`, y habilita el
acceso anónimo de sólo lectura (`GF_AUTH_ANONYMOUS_ENABLED=true`).

El tablero y la fuente anteriores (`DBrd1` y `influxdata-flightsql-datasource`),
que apuntaban al InfluxDB 3 retirado, se eliminaron.

## Primer arranque

```bash
cd docker2
docker compose config --quiet
docker compose up -d influxdb2 grafana mosquitto node-red
```

> No usar `docker compose up -d` sin lista de servicios: el proyecto comparte
> nombres de servicio con otros stacks.

## Verificación rápida

```bash
# Fuente de Grafana sana (4 buckets)
curl -s http://localhost:3000/api/datasources/uid/influxdb/health

# Consulta Flux vía Grafana
curl -s -X POST http://localhost:3000/api/ds/query \
  -H 'Content-Type: application/json' \
  -d '{"queries":[{"refId":"A","datasource":{"type":"influxdb","uid":"influxdb"},
      "query":"from(bucket: \"TGalanDB\") |> range(start: -1h) |> filter(fn: (r) => r._measurement == \"analogas7\") |> last()"}],
      "from":"now-1h","to":"now"}'

# Datos en InfluxDB 2
TOKEN=$(sed -n 's/^INFLUXDB_INIT_ADMIN_TOKEN=//p' .env)
curl -s -X POST "http://localhost:8086/api/v2/query?org=Petrosantander" \
  -H "Authorization: Token $TOKEN" -H 'Content-Type: application/vnd.flux' \
  -H 'Accept: application/csv' \
  --data 'from(bucket: "TGalanDB") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "analogas7") |> last()'
```

Esta migración utiliza únicamente InfluxDB 2. Los datos de la instancia
anterior ya no son necesarios.
