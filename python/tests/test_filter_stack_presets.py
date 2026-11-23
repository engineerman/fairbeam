import unittest

from fairbeam.filter_synthesis.stack_presets import FILTER_STACK_PRESETS, presets_for, resolve_stack


class FilterStackPresetsTests(unittest.TestCase):
    def test_at_least_three_presets_per_kind(self):
        ms = presets_for("microstrip")
        sl = presets_for("stripline")
        self.assertGreaterEqual(len(ms), 3)
        self.assertGreaterEqual(len(sl), 3)
        self.assertTrue(all(p["stack_kind"] == "microstrip" for p in ms))
        self.assertTrue(all(p["stack_kind"] == "stripline" for p in sl))

    def test_python_ts_catalog_size(self):
        """Keep parity with src/designer/filterStackPresets.ts (same id count)."""
        self.assertEqual(len(FILTER_STACK_PRESETS), 6)

    def test_resolve_applies_preset(self):
        stack = resolve_stack({"preset_id": "fr4_ms_160"}, "microstrip")
        self.assertEqual(stack["eps_r"], 4.3)
        self.assertEqual(stack["thickness_mm"], 1.60)

    def test_rejects_mismatched_preset(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_stack({"preset_id": "fr4_sl_320"}, "microstrip")
        self.assertIn("stripline", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
