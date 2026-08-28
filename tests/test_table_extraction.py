import unittest

from table_extraction import build_table_segments, is_combined_scope_aggregate


METRICS = {
    "Scope 1 Emissions": ["scope 1", "gross scope 1 ghg emissions"],
    "Scope 2 Emissions": ["scope 2"],
    "Scope 3 Emissions": ["scope 3"],
    "Energy Consumption": ["energy consumption", "total energy consumption"],
    "Total GHG Emissions": ["ghg emissions", "total ghg emissions", "carbon footprint"],
}
UNITS = {
    "Scope 1 Emissions": ["tCO2e"],
    "Scope 2 Emissions": ["tCO2e"],
    "Scope 3 Emissions": ["tCO2e"],
    "Energy Consumption": ["MWh", "GWh", "kWh"],
    "Total GHG Emissions": ["tCO2e"],
}


class TableExtractionTests(unittest.TestCase):
    def test_hm_year_header_maps_only_historical_columns(self):
        text = "\n".join([
            " " * 44 + "2025          2024          2023          2019          2030",
            "Gross Scope 1 GHG emissions (tCO2e)".ljust(44)
            + "17,039        17,002        17,050        22,738        0.2",
        ])
        rows = build_table_segments(text, 2025, METRICS, UNITS)
        scope_1 = [row for row in rows if row["matched_metrics"] == ["Scope 1 Emissions"]]
        self.assertEqual(
            [(row["table_year"], row["table_value"]) for row in scope_1],
            [("2025", 17039.0), ("2024", 17002.0), ("2023", 17050.0), ("2019", 22738.0)],
        )

    def test_kellanova_exact_table_values_keep_accounting_basis(self):
        text = "\n".join([
            "GHG emissions category (MTCO2e)",
            "Scope 1                         337,470",
            "Scope 2 (Location-based)        339,059",
            "Scope 2 (Market-based)           91,163",
        ])
        rows = build_table_segments(text, 2025, METRICS, UNITS)
        found = {(row["variant"], row["table_value"], row["table_year"]) for row in rows}
        self.assertIn(("default", 337470.0, "2025"), found)
        self.assertIn(("location-based", 339059.0, "2025"), found)
        self.assertIn(("market-based", 91163.0, "2025"), found)

    def test_vestas_wrapped_unit_scales_each_year(self):
        text = "\n".join([
            "Environmental 2025 2024 2023 2022 2021",
            "Scope 2 GHG emissions market-based (1,000 t",
            "CO2e) 1 1 1 2 3",
        ])
        rows = build_table_segments(text, 2025, METRICS, UNITS)
        self.assertEqual(
            [(row["table_year"], row["table_value"], row["variant"]) for row in rows],
            [("2025", 1000.0, "market-based"), ("2024", 1000.0, "market-based"),
             ("2023", 1000.0, "market-based"), ("2022", 2000.0, "market-based"),
             ("2021", 3000.0, "market-based")],
        )

    def test_combined_scope_total_cannot_populate_components(self):
        text = "Combined Scope 1 and market-based Scope 2 emissions amounted to 109 kt CO2e."
        value_start = text.index("109")
        self.assertTrue(is_combined_scope_aggregate(text, value_start, "Scope 1 Emissions"))
        self.assertTrue(is_combined_scope_aggregate(text, value_start, "Scope 2 Emissions"))
        separate = "Scope 1 emissions were 108 kt CO2e, while Scope 2 emissions were 1 kt CO2e."
        self.assertFalse(is_combined_scope_aggregate(separate, separate.index("108"), "Scope 1 Emissions"))

    def test_component_row_does_not_populate_total_ghg(self):
        text = "\n".join([
            "Environmental 2025 2024 2023",
            "Scope 1 GHG emissions (tCO2e) 108 104 99",
        ])
        rows = build_table_segments(text, 2025, METRICS, UNITS)
        self.assertTrue(rows)
        self.assertTrue(all("Total GHG Emissions" not in row["matched_metrics"] for row in rows))


if __name__ == "__main__":
    unittest.main()
