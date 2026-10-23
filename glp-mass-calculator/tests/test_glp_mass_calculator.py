import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from glp_mass_calculator import CalculationError, calculate_glp_ticket
from glp_properties import (
    PropertyError,
    cpl_api_11_2_2,
    ctl_api_11_2_4,
    relative_density_60f,
    vapor_pressure_equilibrium_psig,
)


WATER = 999.016
PROPANO = {
    "observedTempF": 95,
    "observedPressurePSI": 120,
    "observedDensity": 0.4752 * WATER,
    "rvp": 180,
}
BUTANO = {
    "observedTempF": 88.49,
    "observedPressurePSI": 113.52,
    "observedDensity": 0.5618 * WATER,
    "rvp": 44,
}


class PropertyReferenceTests(unittest.TestCase):
    """Valores calculados en 'GENERACIÓN -TIQUETE GLP (1).xlsx'."""

    def test_propano_densidad_60f_tp27(self):
        self.assertAlmostEqual(relative_density_60f(0.4752, 95), 0.5047282177, places=9)

    def test_propano_ctl_api_11_2_4(self):
        sg = relative_density_60f(0.4752, 95)
        self.assertAlmostEqual(ctl_api_11_2_4(sg, 95), 0.9386, places=5)

    def test_propano_pe_y_cpl_api_11_2_2(self):
        sg = relative_density_60f(0.4752, 95)
        pe = vapor_pressure_equilibrium_psig(180, sg, 95)
        self.assertAlmostEqual(pe, 154.0862587, places=6)
        self.assertAlmostEqual(cpl_api_11_2_2(sg, 95, 120, pe), 0.99799, places=5)

    def test_butano_densidad_60f_ctl_pe_cpl(self):
        sg = relative_density_60f(0.5618, 88.49)
        self.assertAlmostEqual(sg, 0.5781013011, places=9)
        self.assertAlmostEqual(ctl_api_11_2_4(sg, 88.49), 0.96774, places=5)
        pe = vapor_pressure_equilibrium_psig(44, sg, 88.49)
        self.assertAlmostEqual(pe, 21.7691404, places=6)
        self.assertAlmostEqual(cpl_api_11_2_2(sg, 88.49, 113.52, pe), 1.00226, places=5)

    def test_densidad_fuera_de_rango_se_rechaza(self):
        with self.assertRaises(PropertyError):
            relative_density_60f(0.9, 95)


class GlpTicketTests(unittest.TestCase):
    def test_propano_volumenes_desde_promedios(self):
        result = calculate_glp_ticket({**PROPANO, "mass_pulses": 20_000, "vapor_mass_pulses": 0})

        self.assertEqual(result["mass_indicated_kg"], 1000)
        self.assertAlmostEqual(result["relative_density_60f"], 0.5047282177, places=9)
        self.assertEqual(result["ctl"], 0.9386)
        self.assertEqual(result["cpl"], 0.99799)
        self.assertEqual(result["ccf"], 0.93671)
        self.assertAlmostEqual(result["gross_volume_us_gal"], 556.46518, places=4)
        self.assertAlmostEqual(result["gsv_us_gal"], result["gross_volume_us_gal"] * 0.93671, places=6)
        self.assertAlmostEqual(result["nsv_us_gal"], result["gsv_us_gal"], places=9)

    def test_butano_volumenes_desde_promedios(self):
        result = calculate_glp_ticket({**BUTANO, "mass_pulses": 20_000, "vapor_mass_pulses": 0})

        self.assertEqual(result["ctl"], 0.96774)
        self.assertEqual(result["cpl"], 1.00226)
        self.assertEqual(result["ccf"], 0.96993)
        self.assertAlmostEqual(result["gsv_us_gal"], result["gross_volume_us_gal"] * 0.96993, places=6)

    def test_k_factor_y_mf_por_defecto(self):
        result = calculate_glp_ticket({**PROPANO, "mass_pulses": 2_000, "vapor_mass_pulses": 0})

        self.assertEqual(result["k_factor_pulses_per_kg"], 20)
        self.assertEqual(result["meter_factor"], 1)
        self.assertEqual(result["mass_indicated_kg"], 100)

    def test_masa_por_pulsos_delta_desde_cero(self):
        result = calculate_glp_ticket(
            {
                **PROPANO,
                "pulse_start": 1_000,
                "pulse_end": 51_000,
                "vapor_mass_pulses": 0,
                "meter_factor": 1.01,
                "sediment_water_pct": 0.5,
            }
        )

        self.assertEqual(result["mass_pulses"], 50_000)
        self.assertEqual(result["mass_indicated_kg"], 2500)
        self.assertAlmostEqual(result["mass_gross_kg"], 2525)
        self.assertAlmostEqual(result["nsv_us_gal"], result["gsv_us_gal"] * 0.995)

    def test_resta_masa_de_vapores(self):
        result = calculate_glp_ticket({**PROPANO, "mass_pulses": 2_000, "vapor_mass_pulses": 400})

        self.assertEqual(result["mass_gross_kg"], 100)
        self.assertEqual(result["vapor_mass_kg"], 20)
        self.assertEqual(result["mass_liquid_gross_kg"], 80)
        self.assertEqual(result["mass_net_kg"], 80)
        self.assertEqual(result["vapor_mass_pulses"], 400)

    def test_rechaza_vapores_mayores_que_masa_principal(self):
        with self.assertRaises(CalculationError):
            calculate_glp_ticket({**PROPANO, "mass_pulses": 100, "vapor_mass_pulses": 200})

    def test_acepta_contador_de_vapores_inicio_y_fin(self):
        result = calculate_glp_ticket(
            {
                **PROPANO,
                "mass_pulses": 2_000,
                "vapor_pulse_start": 10_000,
                "vapor_pulse_end": 10_400,
            }
        )

        self.assertEqual(result["vapor_mass_pulses"], 400)
        self.assertEqual(result["vapor_mass_kg"], 20)

    def test_requiere_pulsos_de_vapores(self):
        with self.assertRaises(CalculationError):
            calculate_glp_ticket({**PROPANO, "mass_pulses": 2_000})

    def test_requiere_promedios_de_proceso(self):
        with self.assertRaises(CalculationError):
            calculate_glp_ticket({"mass_pulses": 2_000, "vapor_mass_pulses": 0, "rvp": 180})

    def test_rechaza_densidad_fuera_de_rango(self):
        with self.assertRaises(CalculationError):
            calculate_glp_ticket({**PROPANO, "observedDensity": 900, "mass_pulses": 2_000, "vapor_mass_pulses": 0})

    def test_rechaza_contador_que_se_reinicia_sin_rollover(self):
        with self.assertRaises(CalculationError):
            calculate_glp_ticket(
                {**PROPANO, "pulse_start": 90_000, "pulse_end": 1_000, "vapor_mass_pulses": 0}
            )

    def test_preserva_metadatos_del_tiquete(self):
        result = calculate_glp_ticket(
            {
                **PROPANO,
                "mass_pulses": 1000,
                "vapor_mass_pulses": 0,
                "request_id": "test-1",
                "ticket": {"cliente": "CLIENTE"},
            }
        )
        self.assertEqual(result["request_id"], "test-1")
        self.assertEqual(result["ticket"], {"cliente": "CLIENTE"})


if __name__ == "__main__":
    unittest.main()
