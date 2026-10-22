"""Cálculo de liquidación GLP partiendo del total de masa por pulsos Coriolis."""

from decimal import Decimal, InvalidOperation
from typing import Any


WATER_DENSITY_60F_KG_M3 = Decimal("999.016")
US_GALLON_M3 = Decimal("0.003785411784")
US_GALLONS_PER_BARREL = Decimal("42")


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
    """Calcula masa y volumen estándar a partir de pulsos del Coriolis.

    Entrada requerida:
      - mass_pulses, o pulse_start y pulse_end (Coriolis principal)
      - vapor_mass_pulses, o vapor_pulse_start y vapor_pulse_end (mismo batch)
      - k_factor_pulses_per_kg (pulsos/kg; 20 para los Coriolis de este gateway)
      - relative_density_60f (gravedad específica a 60°F/60°F)

    La masa de vapores se resta de la masa bruta principal antes de calcular
    volumen liquidable. CTL/CPL no se aplican de nuevo: aquí se mide masa
    directamente y se normaliza con la densidad de referencia.
    """
    if not isinstance(request, dict):
        raise CalculationError("El mensaje debe ser un objeto JSON")

    pulses = _pulse_count(request)
    k_factor = _decimal(request.get("k_factor_pulses_per_kg", 20), "k_factor_pulses_per_kg")
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
    sg60 = _decimal(request.get("relative_density_60f"), "relative_density_60f")
    meter_factor = _decimal(request.get("meter_factor", 1), "meter_factor")
    vapor_meter_factor = _decimal(
        request.get("vapor_meter_factor", meter_factor), "vapor_meter_factor"
    )
    sw_pct = _decimal(request.get("sediment_water_pct", 0), "sediment_water_pct")

    if k_factor <= 0:
        raise CalculationError("k_factor_pulses_per_kg debe ser mayor que cero")
    if vapor_k_factor <= 0:
        raise CalculationError("vapor_k_factor_pulses_per_kg debe ser mayor que cero")
    if not Decimal("0.350") <= sg60 <= Decimal("0.688"):
        raise CalculationError("relative_density_60f debe estar entre 0.350 y 0.688")
    if meter_factor <= 0:
        raise CalculationError("meter_factor debe ser mayor que cero")
    if vapor_meter_factor <= 0:
        raise CalculationError("vapor_meter_factor debe ser mayor que cero")
    if not Decimal("0") <= sw_pct <= Decimal("100"):
        raise CalculationError("sediment_water_pct debe estar entre 0 y 100")

    indicated_mass_kg = pulses / k_factor
    gross_mass_kg = indicated_mass_kg * meter_factor
    vapor_mass_kg = vapor_pulses / vapor_k_factor * vapor_meter_factor
    liquid_gross_mass_kg = gross_mass_kg - vapor_mass_kg
    if liquid_gross_mass_kg < 0:
        raise CalculationError(
            "La masa medida por el Coriolis de vapores no puede superar "
            "la masa del Coriolis principal"
        )
    density_60f_kg_m3 = sg60 * WATER_DENSITY_60F_KG_M3
    density_60f_kg_us_gal = density_60f_kg_m3 * US_GALLON_M3
    gross_standard_us_gal = liquid_gross_mass_kg / density_60f_kg_us_gal
    net_fraction = Decimal("1") - sw_pct / Decimal("100")
    net_mass_kg = liquid_gross_mass_kg * net_fraction
    net_standard_us_gal = gross_standard_us_gal * net_fraction

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
        "relative_density_60f": float(sg60),
        "water_density_60f_kg_m3": float(WATER_DENSITY_60F_KG_M3),
        "product_density_60f_kg_m3": float(density_60f_kg_m3),
        "product_density_60f_kg_us_gal": float(density_60f_kg_us_gal),
        "gsv_us_gal": float(gross_standard_us_gal),
        "nsv_us_gal": float(net_standard_us_gal),
        "gsv_m3": float(gross_standard_us_gal * US_GALLON_M3),
        "nsv_m3": float(net_standard_us_gal * US_GALLON_M3),
        "nsv_l": float(net_standard_us_gal * US_GALLON_M3 * Decimal("1000")),
        "nsv_bbl": float(net_standard_us_gal / US_GALLONS_PER_BARREL),
        "pulsosBatch": int(pulses),
        "kFactor": float(k_factor),
        "formula": "liquid_mass = main_pulses / main_K * main_MF - vapor_pulses / vapor_K * vapor_MF; NSV = liquid_mass * (1 - S&W/100) / (SG60 * 999.016 * 0.003785411784)",
    }

    # Mantener los metadatos originales del tiquete, sin permitir que
    # sobrescriban campos calculados.
    metadata = request.get("ticket")
    if isinstance(metadata, dict):
        result["ticket"] = metadata
    for key in ("request_id", "cliente", "numeroTiquete", "stream", "bala", "operacion", "empresa", "origen", "tipoMedidor", "fechaHora", "observedTempF", "observedPressurePSI", "observedDensity"):
        if key in request:
            result[key] = request[key]

    return result
