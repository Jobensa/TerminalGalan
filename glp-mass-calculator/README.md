# Liquidación GLP por masa Coriolis

Servicio Python que consume solicitudes MQTT con los pulsos del Coriolis y los promedios del batch, y publica la liquidación en `TIQUETE_LPG`.

## Fórmula

Masa (K-factor en pulsos/kg, por defecto 20; MF por defecto 1.000):

```text
masa indicada (kg) = pulsos del batch / K-factor
masa bruta (kg)    = masa indicada × MF
masa líquida (kg)  = masa bruta principal - masa de vapores (TEA)
masa vapores (kg)  = pulsos vapores / K-factor vapores × MF vapores
```

Volúmenes, con los promedios observados del batch:

```text
densidad observada (kg/m³)  = promedio de densidad observada
SG observada                = densidad observada / 999.016
SG 60 °F                    = GPA TP-27 (SG observada, temperatura observada)
CTL                         = API MPMS 11.2.4 (SG 60 °F, temperatura observada)
Pe (psig)                   = API MPMS 11.2.2 (RVP, SG 60 °F, temperatura observada)
CPL                         = API MPMS 11.2.2 (SG 60 °F, temperatura, presión promedio, Pe)
CCF                         = MF × CTL × CPL (5 decimales)
GUV (US gal)                = (masa líquida / densidad observada) m³ ÷ 0.003785411784
GSV (US gal)                = GUV × CCF
NSV (US gal)                = GSV × (1 - S&W/100)
```

Las correlaciones y las tablas de constantes están en `glp_properties.py`. Son las de `docs/GENERACIÓN -TIQUETE GLP (1).xlsx`; las pruebas en `tests/` comparan contra sus valores calculados para propano y butano.

`gsv_mass_check_us_gal` es un cálculo de verificación por masa / densidad a 60 °F. Para propano de referencia difiere del GSV por CCF en aproximadamente 0.5 %; el valor del tiquete es `gsv_us_gal`.

## Entrada MQTT

- Solicitud: `TIQUETE_LPG/CALCULAR`
- Resultado o error: `TIQUETE_LPG`
- QoS: 1, mensajes no retenidos.

Campos requeridos:

| Campo | Descripción |
|---|---|
| `mass_pulses` o `pulse_start`/`pulse_end` | Pulsos del Coriolis principal en el batch (desde cero al iniciar el batch) |
| `observedTempF` | Temperatura observada promedio (°F) |
| `observedPressurePSI` | Presión observada promedio (psig) |
| `observedDensity` | Densidad observada promedio (kg/m³) |
| `rvp` | Presión de vapor Reid (psi) |
| `vapor_mass_pulses` o `vapor_pulse_start`/`vapor_pulse_end` | Pulsos del Coriolis de vapores en el mismo batch (usar `0` si no hubo vapores) |

Campos opcionales: `k_factor_pulses_per_kg` (20), `meter_factor` (1), `vapor_k_factor_pulses_per_kg`, `vapor_meter_factor`, `sediment_water_pct` (0), `fluid`, `cliente`, `numeroTiquete`, `stream`, `bala`, `operacion`, `empresa`, `origen`, `tipoMedidor`, `ticket`.

Ejemplo:

```json
{
  "request_id": "G-2026-0001",
  "mass_pulses": 20000,
  "vapor_mass_pulses": 0,
  "observedTempF": 95,
  "observedPressurePSI": 120,
  "observedDensity": 474.73,
  "rvp": 180,
  "fluid": "propano",
  "cliente": "CLIENTE",
  "numeroTiquete": "G-2026-0001"
}
```

## Ejecución

Desde `docker2/`:

```sh
docker compose up -d --build glp-mass-calculator
```

El servicio usa el broker local en `127.0.0.1:1883` por defecto; los topics, host y puerto se pueden definir por variables de entorno. Pruebas unitarias:

```sh
python -m unittest discover -s glp-mass-calculator/tests
```

Flujo en Node-RED (`flujo-tiquete-lpg`): al cerrar el batch, `Armar solicitud CALCULAR` toma los promedios de `llenado_promedios` y los pulsos de `UIT_2001`/`UIT_2003` de la cisterna seleccionada, publica en `TIQUETE_LPG/CALCULAR` y el resultado vuelve por `TIQUETE_LPG` al UIBUILDER. Si faltan datos, la interfaz muestra el motivo sin enviar la solicitud.
