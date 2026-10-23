"""Cálculo de liquidación GLP partiendo del total de masa por pulsos Coriolis."""

from decimal import Decimal, InvalidOperation
from typing import Any

from glp_properties import (
    PropertyError,
    WATER_DENSITY_60F_KG_M3,
    combined_correction_factor,
    cpl_api_11_2_2,
    ctl_api_11_2_4,
    relative_density_60f,
    vapor_pressure_equilibrium_psig,
)


US_GALLON_M3 = Decimal("0.003785411784")
US_GALLONS_PER_BARREL = Decimal("42")
DEFAULT_K_FACTOR_PULSES_PER_KG = Decimal("20")


class CalculationError(ValueError):
    """La solicitud no contiene datos válidos para la liquidación."""


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise CalculationError(f"{name} debe ser numérico")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise CalculationError(f"{name} debe ser numérico") from None
    if not number.is_finite():
        raise CalculationError(f"{name} debe ser finito")
    return number


def _pulse_count(
    request: dict[str, Any],
    value_key: str = "mass_pulses",
    start_key: str = "pulse_start",
    end_key: str = "pulse_end",
) -> Decimal:
    if value_key in request:
        pulses = _decimal(request[value_key], value_key)
    elif start_key in request and end_key in request:
        start = _decimal(request[start_key], start_key)
        end = _decimal(request[end_key], end_key)
        if end < start:
            raise CalculationError(
                f"{end_key} es menor que {start_key}; indique explícitamente el delta "
                "o implemente el rollover del contador del equipo"
            )
        pulses = end - start
    else:
        raise CalculationError(
            f"Se requiere {value_key} o el par {start_key}/{end_key}"
        )

    if pulses < 0 or pulses != pulses.to_integral_value():
        raise CalculationError(f"{value_key} debe ser entero y no negativo")
    return pulses


def calculate_glp_ticket(request: dict[str, Any]) -> dict[str, Any]:
    """Calcula masa y volúmenes del tiquete GLP a partir de pulsos y promedios del batch.

    Entrada requerida:
      - mass_pulses, o pulse_start y pulse_end (Coriolis principal, desde cero al iniciar el batch)
      - observedTempF: temperatura observada promedio (°F)
      - observedPressurePSI: presión observada promedio (psig)
      - observedDensity: densidad observada promedio (kg/m³)
      - rvp: presión de vapor Reid (psi)

    Entrada opcional:
      - k_factor_pulses_per_kg (por defecto 20), meter_factor (por defecto 1)
      - vapor_mass_pulses, o vapor_pulse_start y vapor_pulse_end (mismo batch)
      - vapor_k_factor_pulses_per_kg y vapor_meter_factor (por defecto los del principal)
      - sediment_water_pct (por defecto 0)

    La densidad a 60 °F, CTL, Pe y CPL se calculan con las correlaciones de
    GPA TP-27 y API MPMS 11.2.2/11.2.4 (ver glp_properties.py). El volumen bruto
    es la masa líquida dividida entre la densidad observada promedio; el volumen
    estándar (GSV) es el bruto por CCF = MF × CTL × CPL.
    """
    if not isinstance(request, dict):
        raise CalculationError("El mensaje debe ser un objeto JSON")

    pulses = _pulse_count(request)
    k_factor = _decimal(request.get("k_factor_pulses_per_kg", DEFAULT_K_FACTOR_PULSES_PER_KG), "k_factor_pulses_per_kg")
    vapor_pulses = _pulse_count(
        request,
        value_key="vapor_mass_pulses",
        start_key="vapor_pulse_start",
        end_key="vapor_pulse_end",
    )
    vapor_k_factor = _decimal(
        request.get("vapor_k_factor_pulses_per_kg", k_factor),
        "vapor_k_factor_pulses_per_kg",
    )
    meter_factor = _decimal(request.get("meter_factor", 1), "meter_factor")
    vapor_meter_factor = _decimal(
        request.get("vapor_meter_factor", meter_factor), "vapor_meter_factor"
    )
    sw_pct = _decimal(request.get("sediment_water_pct", 0), "sediment_water_pct")

    temp_f = _decimal(request.get("observedTempF"), "observedTempF")
    pressure_psig = _decimal(request.get("observedPressurePSI"), "observedPressurePSI")
    observed_density = _decimal(request.get("observedDensity"), "observedDensity")
    rvp = _decimal(request.get("rvp"), "rvp")

    if k_factor <= 0:
        raise CalculationError("k_factor_pulses_per_kg debe ser mayor que cero")
    if vapor_k_factor <= 0:
        raise CalculationError("vapor_k_factor_pulses_per_kg debe ser mayor que cero")
    if meter_factor <= 0:
        raise CalculationError("meter_factor debe ser mayor que cero")
    if vapor_meter_factor <= 0:
        raise CalculationError("vapor_meter_factor debe ser mayor que cero")
    if not Decimal("0") <= sw_pct <= Decimal("100"):
        raise CalculationError("sediment_water_pct debe estar entre 0 y 100")
    if observed_density <= 0:
        raise CalculationError("observedDensity debe ser mayor que cero")
    if rvp <= 0:
        raise CalculationError("rvp debe ser mayor que cero")

    try:
        observed_sg = float(observed_density) / WATER_DENSITY_60F_KG_M3
        sg_60 = relative_density_60f(observed_sg, float(temp_f))
        ctl = ctl_api_11_2_4(sg_60, float(temp_f))
        pe_psig = vapor_pressure_equilibrium_psig(float(rvp), sg_60, float(temp_f))
        cpl = cpl_api_11_2_2(sg_60, float(temp_f), float(pressure_psig), pe_psig)
    except PropertyError as error:
        raise CalculationError(str(error)) from None
    ccf = combined_correction_factor(float(meter_factor), ctl, cpl)

    indicated_mass_kg = pulses / k_factor
    gross_mass_kg = indicated_mass_kg * meter_factor
    vapor_mass_kg = vapor_pulses / vapor_k_factor * vapor_meter_factor
    liquid_gross_mass_kg = gross_mass_kg - vapor_mass_kg
    if liquid_gross_mass_kg < 0:
        raise CalculationError(
            "La masa medida por el Coriolis de vapores no puede superar "
            "la masa del Coriolis principal"
        )
    net_fraction = Decimal("1") - sw_pct / Decimal("100")
    net_mass_kg = liquid_gross_mass_kg * net_fraction

    gross_m3 = float(liquid_gross_mass_kg) / float(observed_density)
    gross_us_gal = gross_m3 / float(US_GALLON_M3)
    indicated_us_gal = gross_us_gal / float(meter_factor)
    standard_us_gal = gross_us_gal * ccf
    net_standard_us_gal = standard_us_gal * float(net_fraction)

    density_60f_kg_m3 = sg_60 * WATER_DENSITY_60F_KG_M3
    mass_check_us_gal = float(liquid_gross_mass_kg) / (density_60f_kg_m3 * float(US_GALLON_M3))

    result = {
        "calculation": "coriolis_mass_pulses_to_glp_standard_volume",
        "basis": "60F",
        "fluid": request.get("fluid"),
        "mass_pulses": int(pulses),
        "k_factor_pulses_per_kg": float(k_factor),
        "mass_indicated_kg": float(indicated_mass_kg),
        "meter_factor": float(meter_factor),
        "mass_gross_kg": float(gross_mass_kg),
        "vapor_mass_pulses": int(vapor_pulses),
        "vapor_k_factor_pulses_per_kg": float(vapor_k_factor),
        "vapor_meter_factor": float(vapor_meter_factor),
        "vapor_mass_kg": float(vapor_mass_kg),
        "mass_liquid_gross_kg": float(liquid_gross_mass_kg),
        "sediment_water_pct": float(sw_pct),
        "mass_net_kg": float(net_mass_kg),
        "observed_density_kg_m3": float(observed_density),
        "observed_relative_density": observed_sg,
        "relative_density_60f": sg_60,
        "ctl": ctl,
        "vapor_pressure_equilibrium_psig": pe_psig,
        "cpl": cpl,
        "ccf": ccf,
        "water_density_60f_kg_m3": WATER_DENSITY_60F_KG_M3,
        "product_density_60f_kg_m3": density_60f_kg_m3,
        "indicated_volume_us_gal": indicated_us_gal,
        "gross_volume_us_gal": gross_us_gal,
        "gsv_us_gal": standard_us_gal,
        "gsv_mass_check_us_gal": mass_check_us_gal,
        "nsv_us_gal": net_standard_us_gal,
        "gsv_m3": standard_us_gal * float(US_GALLON_M3),
        "nsv_m3": net_standard_us_gal * float(US_GALLON_M3),
        "nsv_l": net_standard_us_gal * float(US_GALLON_M3) * 1000,
        "nsv_bbl": net_standard_us_gal / float(US_GALLONS_PER_BARREL),
        "pulsosBatch": int(pulses),
        "kFactor": float(k_factor),
        "formula": (
            "masa_liquida = pulsos/K*MF - pulsos_vapor/K_vapor*MF_vapor; "
            "GUV = masa_liquida / densidad_observada; GSV = GUV * CCF; "
            "CCF = MF*CTL(API 11.2.4)*CPL(API 11.2.2); "
            "SG60 = GPA TP-27"
        ),
    }

    # Mantener los metadatos originales del tiquete, sin permitir que
    # sobrescriban campos calculados.
    metadata = request.get("ticket")
    if isinstance(metadata, dict):
        result["ticket"] = metadata
    for key in ("request_id", "cliente", "numeroTiquete", "stream", "bala", "operacion", "empresa", "origen", "tipoMedidor", "fechaHora", "observedTempF", "observedPressurePSI", "observedDensity", "rvp"):
        if key in request:
            result[key] = request[key]

    return result
