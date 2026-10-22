import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from glp_mass_calculator import CalculationError, calculate_glp_ticket


class GlpMassCalculatorTests(unittest.TestCase):
    def test_converts_coriolis_pulses_to_standard_volume(self):
        result = calculate_glp_ticket(
            {
                "mass_pulses": 100_000,
                "k_factor_pulses_per_kg": 1000,
                "vapor_mass_pulses": 0,
                "relative_density_60f": 0.534,
            }
        )

        self.assertEqual(result["mass_indicated_kg"], 100)
        self.assertAlmostEqual(result["product_density_60f_kg_m3"], 533.474544)
        self.assertAlmostEqual(result["nsv_us_gal"], 49.51915, places=5)
        self.assertEqual(result["mass_net_kg"], result["mass_gross_kg"])

    def test_matches_volumen_neto_estandar_workbook_example(self):
        # El Excel muestra 22.20285 millones de pulsos y multiplica por 1000.
        # En pulsos enteros del contador Coriolis equivale a 22,202,850 pulsos;
        # el K-factor 1000 pulsos/kg se divide para obtener la masa.
        result = calculate_glp_ticket(
            {
                "mass_pulses": 22_202_850,
                "k_factor_pulses_per_kg": 1000,
                "vapor_mass_pulses": 0,
                "relative_density_60f": 0.572649,
            }
        )

        self.assertAlmostEqual(result["mass_indicated_kg"], 22_202.85)
        # El Excel da 10,252.655614 gal; usamos 999.016 kg/m³ del tiquete
        # principal frente a 999.012 kg/m³ de esta hoja nueva.
        self.assertAlmostEqual(result["nsv_us_gal"], 10_252.61489, places=5)
        self.assertLess(abs(result["nsv_us_gal"] - 10_252.655614), 0.05)

    def test_calculates_delta_from_cumulative_counter_and_applies_meter_factor(self):
        result = calculate_glp_ticket(
            {
                "pulse_start": 1_000,
                "pulse_end": 51_000,
                "k_factor_pulses_per_kg": 1000,
                "vapor_mass_pulses": 0,
                "relative_density_60f": 0.534,
                "meter_factor": 1.01,
                "sediment_water_pct": 0.5,
            }
        )

        self.assertEqual(result["mass_pulses"], 50_000)
        self.assertEqual(result["mass_indicated_kg"], 50)
        self.assertEqual(result["mass_gross_kg"], 50.5)
        self.assertAlmostEqual(result["mass_net_kg"], 50.2475)
        self.assertAlmostEqual(result["nsv_us_gal"], result["gsv_us_gal"] * 0.995)

    def test_subtracts_vapor_mass_from_main_coriolis_for_liquid_ticket(self):
        result = calculate_glp_ticket(
            {
                "mass_pulses": 2_000,
                "vapor_mass_pulses": 400,
                "relative_density_60f": 0.534,
            }
        )

        self.assertEqual(result["mass_gross_kg"], 100)
        self.assertEqual(result["vapor_mass_kg"], 20)
        self.assertEqual(result["k_factor_pulses_per_kg"], 20)
        self.assertEqual(result["vapor_k_factor_pulses_per_kg"], 20)
        self.assertEqual(result["mass_liquid_gross_kg"], 80)
        self.assertEqual(result["mass_net_kg"], 80)
        self.assertEqual(result["vapor_mass_pulses"], 400)

    def test_rejects_vapor_mass_greater_than_main_coriolis_mass(self):
        with self.assertRaises(CalculationError):
            calculate_glp_ticket(
                {
                    "mass_pulses": 100,
                    "k_factor_pulses_per_kg": 20,
                    "vapor_mass_pulses": 200,
                    "relative_density_60f": 0.534,
                }
            )

    def test_accepts_vapor_counter_start_and_end_values(self):
        result = calculate_glp_ticket(
            {
                "mass_pulses": 2_000,
                "k_factor_pulses_per_kg": 20,
                "vapor_pulse_start": 10_000,
                "vapor_pulse_end": 10_400,
                "relative_density_60f": 0.534,
            }
        )

        self.assertEqual(result["vapor_mass_pulses"], 400)
        self.assertEqual(result["vapor_mass_kg"], 20)

    def test_requires_vapor_pulse_delta_for_final_liquid_ticket(self):
        with self.assertRaises(CalculationError):
            calculate_glp_ticket(
                {
                    "mass_pulses": 2_000,
                    "k_factor_pulses_per_kg": 20,
                    "relative_density_60f": 0.534,
                }
            )

    def test_preserves_ticket_metadata(self):
        result = calculate_glp_ticket(
            {
                "mass_pulses": 1000,
                "vapor_mass_pulses": 0,
                "relative_density_60f": 0.55,
                "request_id": "test-1",
                "ticket": {"cliente": "CLIENTE"},
            }
        )
        self.assertEqual(result["request_id"], "test-1")
        self.assertEqual(result["ticket"], {"cliente": "CLIENTE"})

    def test_rejects_counter_reset_without_explicit_rollover(self):
        with self.assertRaises(CalculationError):
            calculate_glp_ticket(
                {
                    "pulse_start": 90_000,
                    "pulse_end": 1_000,
                    "vapor_mass_pulses": 0,
                    "relative_density_60f": 0.55,
                }
            )


if __name__ == "__main__":
    unittest.main()
