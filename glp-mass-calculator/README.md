# Liquidación GLP por masa Coriolis

Servicio Python que consume solicitudes MQTT con conteo de pulsos del Coriolis y publica la liquidación en `TIQUETE_LPG`.

## Fórmula

El K-factor configurado en el Coriolis se expresa como **pulsos/kg**:

```text
masa indicada (kg) = delta de pulsos / K-factor
masa corregida (kg) = masa indicada × factor del medidor
masa líquida bruta (kg) = masa principal corregida - masa vapores corregida
masa vapores (kg) = pulsos vapores / K-factor vapores × factor medidor vapores
density_60F (kg/m³) = SG60 × 999.016
kg/US gal a 60°F = density_60F × 0.003785411784
GSV líquido (US gal) = masa líquida bruta / (kg/US gal a 60°F)
NSV (US gal) = GSV líquido × (1 - S&W/100)
```

El tiquete final requiere el delta `vapor_mass_pulses` del Coriolis de vapores,
medido durante el mismo batch que `mass_pulses` del Coriolis principal. Se resta
la masa de vapores (enviada a la TEA) de la masa del principal antes de calcular
el volumen liquidable. El K-factor y M-factor del vapor usan por defecto los del
medidor principal; se pueden especificar `vapor_k_factor_pulses_per_kg` y
`vapor_meter_factor` si difieren. Si no hubo vapores, enviar explícitamente
`vapor_mass_pulses: 0`; la liquidación se rechaza si falta el dato.

CTL y CPL del Excel corrigen un volumen medido a las condiciones observadas. Para masa medida directamente por Coriolis esas correcciones no se multiplican otra vez: se convierte la masa a volumen estándar con la densidad de referencia a 60°F. El `relative_density_60f` debe venir del análisis/especificación del producto o de una densidad certificada a esa condición; no se infiere de densidad observada sin una corrección API adecuada.

## MQTT

- Solicitud: `TIQUETE_LPG/CALCULAR`
- Resultado o error: `TIQUETE_LPG`
- QoS: 1, mensajes no retenidos.

Ejemplo publicable con `mosquitto_pub`:

```json
{
  "request_id": "G-2026-0001",
  "mass_pulses": 2000,
  "k_factor_pulses_per_kg": 20,
  "vapor_mass_pulses": 400,
  "vapor_k_factor_pulses_per_kg": 20,
  "relative_density_60f": 0.534,
  "meter_factor": 1.0,
  "sediment_water_pct": 0,
  "fluid": "propano",
  "cliente": "CLIENTE",
  "numeroTiquete": "G-2026-0001",
  "stream": "1",
  "bala": "BA-1",
  "operacion": "Ventas",
  "ticket": {
    "temperatura_promedio_f": 95,
    "presion_promedio_psig": 120
  }
}
```

También se aceptan totalizadores acumulativos: `pulse_start`/`pulse_end` para el
principal y `vapor_pulse_start`/`vapor_pulse_end` para vapores, en lugar de los
deltas respectivos. Los deltas deben cubrir exactamente el mismo batch. Un
contador que se reinicia requiere tratar el rollover en el origen y enviar el
delta no negativo. Los metadatos de temperatura y presión se conservan para
trazabilidad, pero no alteran la conversión de masa a volumen estándar.

## Verificación con `docs/Calculo de volumen@60.xlsx`

La hoja **“Volumen Neto estandar”** respalda la conversión directa masa → volumen a 60 °F: usa SG60, densidad del agua a 60 °F, y divide la masa por kg/gal. Hay una inconsistencia de unidades en sus celdas de pulsos: indica `B2 = 22.20285 pulsos`, `K = 1000 pulsos/kg`, pero calcula masa como `B2 × K`. Ese resultado solo es coherente si B2 está expresado en **millones de pulsos**. Para un contador que entrega pulsos enteros, se deben enviar `22,202,850` y calcular `22,202,850 / 1,000 = 22,202.85 kg`.

Con esos pulsos y `SG60 = 0.572649`, el servicio calcula `NSV = 10,252.61489 U.S. gal`; la hoja obtiene `10,252.65561 U.S. gal`. La diferencia de `0.04072 gal` (0.00040 %) proviene de que esta hoja usa `999.012 kg/m³` y el tiquete de liquidación anterior usa `999.016 kg/m³`; se conservó el valor del tiquete principal.

La hoja **“API 11.2.4”** es la ruta alternativa basada en volumen: usa K-factor de `14,000 pulsos/bbl`, obtiene IV `10,522.677 gal` y GSV `10,271.81638 gal` con CTL/CPL. No es una comparación exacta con la otra hoja: emplea otro K-factor, otro conteo/escala de pulsos y SG60 `0.5708` en lugar de `0.572649`. Además, calcula su masa R51 con la densidad relativa observada y el IV. Para validar masa Coriolis, se debe comparar con el conteo entero de pulsos y el SG60 correspondiente al mismo lote.

La respuesta incluye masa indicada/corregida/neta, densidad de referencia, GSV/NSV en galones y m³, litros netos y barriles netos; además conserva los datos de identificación del tiquete.

## Ejecución

Desde `docker2/`:

```sh
docker compose up -d --build glp-mass-calculator
```

El servicio usa el broker local en `127.0.0.1:1883` por defecto; los topics, host y puerto se pueden definir por variables de entorno. Pruebas unitarias:

```sh
python -m unittest discover -s glp-mass-calculator/tests
```

Node-RED escucha el topic `TIQUETE_LPG` y entrega el resultado al UIBUILDER. El flujo existente de generación de tiquetes aún tiene `pulsosBatch` y `kFactor` fijos en un ejemplo y su consulta SQLite devuelve promedios de flujo; no se encontró en el proyecto un tag/columna con el delta real del contador de pulsos del Coriolis. Por eso, el origen de pulsos debe publicar la solicitud JSON de arriba en `TIQUETE_LPG/CALCULAR`; no se debe reutilizar el valor de ejemplo del flujo como conteo real.
