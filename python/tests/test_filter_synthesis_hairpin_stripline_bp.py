import unittest

from fairbeam.design import check_design
from fairbeam.filter_synthesis.hairpin_stripline_bp import (
    DEFAULT_HAIRPIN_STRIPLINE_BP,
    HairpinStriplineBpSpec,
    synthesize_hairpin_stripline_bp,
)


class FilterSynthesisHairpinStriplineBpTests(unittest.TestCase):
    def test_synthesize_order3_sandwich_grounds(self):
        spec = HairpinStriplineBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9)
        result = synthesize_hairpin_stripline_bp(spec)
        design = result.design
        check_design(design)
        part_names = {p["name"] for p in design["parts"]}
        self.assertIn("gnd_top", part_names)
        self.assertIn("gnd_bottom", part_names)
        self.assertEqual(len(design.get("ports", [])), 2)
        gap_keys = [d["key"] for d in result.dimensions if d["key"].startswith("gap")]
        self.assertEqual(len(gap_keys), spec.order)
        sp_keys = [d["key"] for d in result.dimensions if d["key"].startswith("sp")]
        self.assertEqual(len(sp_keys), spec.order - 1)

    def test_default_spec(self):
        self.assertEqual(DEFAULT_HAIRPIN_STRIPLINE_BP.order, 3)

    def test_registry_topology(self):
        from fairbeam.filter_synthesis import list_topologies, synthesize

        ids = {t["id"] for t in list_topologies()}
        self.assertIn("hairpin_stripline_bp", ids)
        result = synthesize(
            "hairpin_stripline_bp",
            {"electrical": {"f0_hz": 2e9, "order": 3, "bw_ghz": 0.2}, "stack": {"thickness_mm": 3.2, "eps_r": 2.2}},
        )
        check_design(result.design)


if __name__ == "__main__":
    unittest.main()
