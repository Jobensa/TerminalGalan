"""Propiedades del GLP (propano/butano) para liquidación por masa.

Replica las hojas de cálculo de `docs/GENERACIÓN -TIQUETE GLP (1).xlsx`:
- Densidad relativa a 60 °F: GPA TP-27 (hojas "C3/C4 DR @ 60°F").
- CTL: API MPMS 11.2.4 (hojas "C3/C4 CTL", celda AK102).
- Presión de equilibrio (Pe) y CPL: API MPMS 11.2.2 (hojas "C3/C4 CTL", AT73-AT80).

Los exponentes y las tablas de constantes son los del libro; las pruebas
comparan contra sus valores calculados.
"""

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


WATER_DENSITY_60F_KG_M3 = 999.016

# (nombre, γ60, Tc [°R], Zc, ρc, K1, K2, K3, K4) — hoja "REFERENCE FLUIDS".
REFERENCE_FLUIDS = (
    ("EE (68/32)", 0.325022, 298.11, 0.27998, 6.25, 2.54616855327, -0.058244177754, 0.803398090807, -0.745720314137),
    ("Ethane", 0.355994, 305.33, 0.2822, 6.87, 1.8911304261, -0.370305782347, -0.54486728872, 0.337876634952),
    ("EP (65/35)", 0.429277, 333.67, 0.2806, 5.615, 2.20970078464, -0.294253708172, -0.405754420098, 0.319443433421),
    ("EP (35/65)", 0.470381, 352.46, 0.2793, 5.11, 2.2534198132, -0.266542138024, -0.372756711655, 0.384734185665),
    ("Propane", 0.507025, 369.78, 0.27626, 5, 1.96568366933, -0.327662435541, -0.417979702538, 0.303271602831),
    ("i-Butane", 0.562827, 407.85, 0.28326, 3.86, 2.0474803441, -0.289734363425, -0.330345036434, 0.291757103132),
    ("n-Butane", 0.584127, 425.16, 0.27536, 3.92, 2.03734743118, -0.299059145695, -0.418883095671, 0.380367738748),
    ("i-Pentane", 0.624285, 460.44, 0.27026, 3.247, 2.06541640707, -0.23836620884, -0.161440492247, 0.258681568613),
    ("n-Pentane", 0.631054, 469.65, 0.27235, 3.2, 2.11263474494, -0.26126941356, -0.291923445075, 0.308344290017),
    ("i-Hexane", 0.657167, 498.05, 0.26706, 2.727, 2.02382197871, -0.423550090067, -1.15281098257, 0.950139001678),
    ("n-Hexane", 0.664064, 507.35, 0.26762, 2.704, 2.17134547773, -0.232997313405, -0.267019794036, 0.378629524102),
    ("n-Heptane", 0.688039, 540.15, 0.26312, 2.315, 2.19773533433, -0.275056764147, -0.447144095029, 0.493770995799),
)

# (γ60 mínimo, A0, A1, B0, B1) — hoja "C3 CTL", AS63:AW67 (API 11.2.2).
PE_COEFFICIENTS = (
    (0.49, -6.4747, 37.083, 12038, -31296.5),
    (0.51, 11.5454, 1.749, 1378.8, -10396.1),
    (0.56, 6.4827, 10.79, 3721.5, -14579.5),
    (0.585, 6.5412, 10.69, 6514.5, -19353.9),
    (0.625, 20.8537, -12.21, -6765.6, 1894.3),
)

RANGE_TP27_SG = (0.350, 0.688)
RANGE_CPL_SG = (0.350, 0.637)
RANGE_CPL_TEMP_F = (-50.0, 140.0)
RANGE_PRESSURE_PSIG = (0.0, 2200.0)


class PropertyError(ValueError):
    """Los valores de entrada están fuera del rango de las correlaciones."""


def round_excel(value: float, decimals: int) -> float:
    """ROUND de Excel: redondeo a la mitad, alejándose de cero."""
    quantum = Decimal(1).scaleb(-decimals)
    return float(Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _saturated_density(fluid: tuple, reduced_temp: float, denom_exponent: float) -> float:
    """Densidad saturada reducida (Hankinson-Thomson), con la forma de las hojas."""
    _, _, _, _, rho_c, k1, k2, k3, k4 = fluid
    tau = 1.0 - reduced_temp
    numerator = k1 * tau ** 0.35 + k3 * tau ** 2 + k4 * tau ** 3
    return rho_c * (1.0 + numerator / (1.0 + k2 * tau ** denom_exponent))


def relative_density_60f(observed_sg: float, temp_f: float) -> float:
    """Densidad relativa a 60 °F a partir de la densidad relativa observada (GPA TP-27)."""
    if not RANGE_TP27_SG[0] <= observed_sg <= RANGE_TP27_SG[1]:
        raise PropertyError(
            f"densidad relativa observada {observed_sg:.4f} fuera de "
            f"{RANGE_TP27_SG[0]:.3f}-{RANGE_TP27_SG[1]:.3f}"
        )

    t_x = (temp_f + 459.67) / 1.8
    reference = []
    for fluid in REFERENCE_FLUIDS:
        tc = fluid[2]
        rho_x = _saturated_density(fluid, t_x / tc, 0.05) if t_x < tc else None
        rho_60 = _saturated_density(fluid, 519.67 / (1.8 * tc), 0.05)
        sg_x = fluid[1] * rho_x / rho_60 if rho_x is not None else None
        reference.append((fluid, rho_x, rho_60, sg_x))

    candidates = [i for i, (_, _, _, sg_x) in enumerate(reference) if sg_x is not None and sg_x <= observed_sg]
    if not candidates:
        raise PropertyError("no hay fluido de referencia por debajo de la densidad observada")
    low = max(candidates, key=lambda i: reference[i][3])
    if low + 1 >= len(REFERENCE_FLUIDS) or reference[low + 1][3] is None:
        raise PropertyError("no hay fluido de referencia por encima de la densidad observada")
    high = low + 1

    fluid_lo, rho_x_lo, rho_60_lo, sg_x_lo = reference[low]
    fluid_hi, rho_x_hi, rho_60_hi, sg_x_hi = reference[high]
    g_lo, g_hi = fluid_lo[1], fluid_hi[1]
    tc_lo, tc_hi = fluid_lo[2], fluid_hi[2]
    h_z = (fluid_lo[3] * fluid_lo[4]) / (fluid_hi[3] * fluid_hi[4])

    b35 = (observed_sg - sg_x_lo) / (sg_x_hi - sg_x_lo)
    c35 = g_lo + b35 * (g_hi - g_lo)
    d35 = (c35 - g_lo) / (g_hi - g_lo)
    i35 = rho_60_lo / (1 + d35 * ((rho_60_lo / (h_z * rho_60_hi)) - 1))
    j35 = rho_x_lo / (i35 * (1 + d35 * ((rho_x_lo / (h_z * rho_x_hi)) - 1)))
    k35 = j35 * c35

    b39 = g_hi - g_lo
    c39 = sg_x_hi ** 2 - sg_x_lo ** 2
    d39 = (sg_x_hi - sg_x_lo) / (k35 - sg_x_lo)
    e39 = (b39 - d39 * (c35 - g_lo)) / (c39 - d39 * (k35 ** 2 - sg_x_lo ** 2))
    f39 = (b39 - e39 * c39) / (sg_x_hi - sg_x_lo)
    g39 = g_lo - f39 * sg_x_lo - e39 * sg_x_lo ** 2
    sg_60 = e39 * observed_sg ** 2 + f39 * observed_sg + g39

    i39 = (sg_60 - g_lo) / (g_hi - g_lo)
    tc_39 = tc_lo + i39 * (tc_hi - tc_lo)
    n39 = rho_60_lo / (1 + i39 * (rho_60_lo / (h_z * rho_60_hi) - 1))
    o39 = rho_x_lo / (n39 * (1 + i39 * (rho_x_lo / (h_z * rho_x_hi) - 1)))
    if not math.isfinite(sg_60) or abs(o39 * sg_60 - observed_sg) > 1e-6:
        raise PropertyError("la iteración de densidad a 60 °F no convergió")
    return sg_60


def ctl_api_11_2_4(sg_60: float, temp_f: float) -> float:
    """Factor de corrección de temperatura CTL (API MPMS 11.2.4)."""
    if not RANGE_CPL_TEMP_F[0] <= temp_f <= RANGE_CPL_TEMP_F[1]:
        raise PropertyError(f"temperatura {temp_f} °F fuera de {RANGE_CPL_TEMP_F[0]:.0f} a {RANGE_CPL_TEMP_F[1]:.0f} °F")
    sg_r = round_excel(sg_60, 4)
    t_k = round_excel(temp_f, 1)
    t_k = (t_k + 459.67) / 1.8

    lows = [i for i, fluid in enumerate(REFERENCE_FLUIDS) if fluid[1] <= sg_r]
    if not lows or lows[-1] + 1 >= len(REFERENCE_FLUIDS):
        raise PropertyError("densidad a 60 °F fuera de la tabla de fluidos de referencia")
    low = lows[-1]
    fluid_lo, fluid_hi = REFERENCE_FLUIDS[low], REFERENCE_FLUIDS[low + 1]

    delta = (sg_r - fluid_lo[1]) / (fluid_hi[1] - fluid_lo[1])
    tc_mid = fluid_lo[2] + delta * (fluid_hi[2] - fluid_lo[2])
    tr_x = t_k / tc_mid
    tr_60 = 519.67 / (1.8 * tc_mid)
    h_z = (fluid_lo[3] * fluid_lo[4]) / (fluid_hi[3] * fluid_hi[4])

    def rho(fluid: tuple, tr: float) -> float:
        return _saturated_density(fluid, tr, 0.65)

    rho_60_lo, rho_60_hi = rho(fluid_lo, tr_60), rho(fluid_hi, tr_60)
    rho_x_lo, rho_x_hi = rho(fluid_lo, tr_x), rho(fluid_hi, tr_x)
    x = rho_60_lo / (1 + delta * (rho_60_lo / (h_z * rho_60_hi) - 1))
    ctl = rho_x_lo / (x * (1 + delta * (rho_x_lo / (h_z * rho_x_hi) - 1)))
    return round_excel(ctl, 5)


def vapor_pressure_equilibrium_psig(rvp_psi: float, sg_60: float, temp_f: float) -> float:
    """Presión de equilibrio Pe en psig (API MPMS 11.2.2)."""
    matches = [row for row in PE_COEFFICIENTS if row[0] <= sg_60]
    if not matches:
        raise PropertyError(f"densidad a 60 °F {sg_60:.4f} fuera de la tabla de presión de vapor")
    _, _, _, b0, b1 = matches[-1]
    if rvp_psi <= 0:
        raise PropertyError("RVP debe ser mayor que cero")
    exponent = (b0 + b1 * sg_60) * (100.0 - temp_f) / (543.0 * (temp_f + 443.0))
    pe_psia = math.exp(math.log(rvp_psi) + exponent)
    return pe_psia - 14.7


def cpl_api_11_2_2(sg_60: float, temp_f: float, pressure_psig: float, pe_psig: float) -> float:
    """Factor de corrección de presión CPL (API MPMS 11.2.2)."""
    if not RANGE_CPL_SG[0] <= sg_60 <= RANGE_CPL_SG[1]:
        raise PropertyError(f"densidad a 60 °F {sg_60:.4f} fuera de {RANGE_CPL_SG[0]:.3f}-{RANGE_CPL_SG[1]:.3f}")
    if not RANGE_CPL_TEMP_F[0] <= temp_f <= RANGE_CPL_TEMP_F[1]:
        raise PropertyError(f"temperatura {temp_f} °F fuera de {RANGE_CPL_TEMP_F[0]:.0f} a {RANGE_CPL_TEMP_F[1]:.0f} °F")
    if not RANGE_PRESSURE_PSIG[0] <= pressure_psig <= RANGE_PRESSURE_PSIG[1]:
        raise PropertyError(f"presión {pressure_psig} psig fuera de 0 a 2200 psig")

    t_r = temp_f + 459.7
    s = sg_60
    a = (
        -(t_r ** 2 * 2.1465891e-6)
        + (t_r ** 2 * s ** 2 * 1.577439e-5)
        - (t_r ** 2 * s ** 4 * 1.0502139e-5)
        + (t_r ** 3 * s ** 6 * 2.8324481e-7)
        - 0.95495939
        + (t_r ** 3 * s ** 2 * 7.2900662e-8)
        - (t_r ** 3 * s ** 4 * 2.7769343e-7)
        + (t_r * s ** 2 * 0.03645838)
        - (t_r * s * 0.05110158)
        + (t_r * 0.00795529)
        + (s * 9.1311491)
    )
    b = (
        -((6.0357667e-10) * (t_r ** 2))
        + (t_r * s ** 2 * 2.2112678e-6)
        + (s * 0.00088384)
        - (s ** 2 * 0.00204016)
    )
    a_round = round_excel(a * 100000, 0)
    b_round = round_excel(b * 100000, 3)
    delta_p = pressure_psig - pe_psig
    c = round_excel(1 / (a_round + delta_p * b_round), 8)
    return round_excel(1 / (1 - c * delta_p), 5)


def combined_correction_factor(mf: float, ctl: float, cpl: float) -> float:
    """CCF = MF × CTL × CPL, redondeado a 5 decimales como en el libro."""
    return round_excel(mf * ctl * cpl, 5)
