"""Parity: TS Run-dialog preview frozen strings match emerge_port_map APPROX_* / MAPPED_*.

Expected preview lines are locked here against Python constants (no front-end unit runner).
Loads emerge_port_map by file path so this gate does not require CSXCAD/openEMS DLLs.
"""
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TS_PATH = ROOT / "src" / "designer" / "emergePortMapPreview.ts"
PY_PATH = ROOT / "python" / "fairbeam" / "emerge_port_map.py"


def _load_emerge_port_map():
    spec = importlib.util.spec_from_file_location("emerge_port_map_parity", PY_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_epm = _load_emerge_port_map()
APPROX_DRIVEN_LUMPED = _epm.APPROX_DRIVEN_LUMPED
APPROX_PLANAR_MICROSTRIP = _epm.APPROX_PLANAR_MICROSTRIP
APPROX_PLANAR_MICROSTRIP_MODAL = _epm.APPROX_PLANAR_MICROSTRIP_MODAL
APPROX_PLANAR_CPW = _epm.APPROX_PLANAR_CPW
APPROX_PLANAR_CPW_MODAL = _epm.APPROX_PLANAR_CPW_MODAL
APPROX_PLANAR_LUMPED = _epm.APPROX_PLANAR_LUMPED
APPROX_COAX_TEM = _epm.APPROX_COAX_TEM
MAPPED_LUMPED = _epm.MAPPED_LUMPED
MAPPED_WAVE = _epm.MAPPED_WAVE
MAPPED_COAX = _epm.MAPPED_COAX

# Minimal expected-line fixture. OK lines show mapped BC only (no APPROX parenthetical);
# APPROX_* still parity-checked as TS string constants against Python.
# Planar microstrip defaults to LumpedPort; WavePort when accept_modal_ports wins.
# Planar CPW needs accept (modal → WavePort; lumped → LumpedPort).
EXPECTED_LINES = [
    {
        "path": "driven",
        "ports": [{"number": 1, "type": "lumped"}],
        "ok": True,
        "lines": [f"Port 1 · lumped → {MAPPED_LUMPED}"],
    },
    {
        "path": "planar",
        "ports": [{"number": 1, "type": "microstrip"}],
        "ok": True,
        "lines": [f"Port 1 · microstrip → {MAPPED_LUMPED}"],
    },
    {
        "path": "planar",
        "ports": [{"number": 1, "type": "microstrip"}],
        "accept": {"accept_modal_ports": True},
        "ok": True,
        "lines": [f"Port 1 · microstrip → {MAPPED_WAVE}"],
    },
    {
        "path": "planar",
        "ports": [{"number": 1, "type": "microstrip"}],
        "accept": {"accept_modal_ports": True, "accept_lumped_terminals": True},
        "ok": True,
        "lines": [f"Port 1 · microstrip → {MAPPED_WAVE}"],
    },
    {
        "path": "planar",
        "ports": [{"number": 1, "type": "cpw"}],
        "ok": False,
        "lines": ["Port 1 · cpw → accept_modal_ports required"],
    },
    {
        "path": "planar",
        "ports": [{"number": 1, "type": "cpw"}],
        "accept": {"accept_modal_ports": True},
        "ok": True,
        "lines": [f"Port 1 · cpw → {MAPPED_WAVE}"],
    },
    {
        "path": "planar",
        "ports": [{"number": 1, "type": "cpw"}],
        "accept": {"accept_modal_ports": True, "accept_lumped_terminals": True},
        "ok": True,
        "lines": [f"Port 1 · cpw → {MAPPED_WAVE}"],
    },
    {
        "path": "planar",
        "ports": [{"number": 1, "type": "cpw"}],
        "accept": {"accept_lumped_terminals": True},
        "ok": True,
        "lines": [f"Port 1 · cpw → {MAPPED_LUMPED}"],
    },
    {
        "path": "planar",
        "ports": [{"number": 1, "type": "lumped"}],
        "ok": True,
        "lines": [f"Port 1 · lumped → {MAPPED_LUMPED}"],
    },
    {
        "path": "coax",
        "ports": [{"number": 1, "type": "coaxial"}],
        "ok": True,
        "lines": [f"Port 1 · coaxial → {MAPPED_COAX}"],
    },
    {
        "path": "driven",
        "ports": [{"number": 1, "type": "microstrip"}],
        "ok": False,
        "lines": ["Port 1 · microstrip → does not admit microstrip"],
    },
    {
        "path": "driven",
        "ports": [{"number": 1, "type": "cpw"}],
        "ok": False,
        "lines": ["Port 1 · cpw → does not admit CPW"],
    },
    {
        "path": "driven",
        "ports": [{"number": 2, "type": "waveguide"}],
        "ok": False,
        "lines": ["Port 2 · waveguide → not supported on this path"],
    },
    {
        "path": "planar",
        "ports": [{"number": 1, "type": "coaxial"}],
        "ok": False,
        "lines": ["Port 1 · coaxial → not supported on this path"],
    },
]


def _ts_string_const(src: str, name: str) -> str:
    """Scrape export const NAME = \"...\" (single- or next-line). Keep UTF-8 as-is."""
    m = re.search(
        rf'export const {re.escape(name)}\s*=\s*"([^"]*)"',
        src,
    )
    if m:
        return m.group(1)
    m = re.search(
        rf'export const {re.escape(name)}\s*=\s*\n\s*"([^"]*)"',
        src,
    )
    if m:
        return m.group(1)
    raise AssertionError(f"Could not find export const {name} in {TS_PATH}")


class StringParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = TS_PATH.read_text(encoding="utf-8")

    def test_mapped_lumped(self):
        self.assertEqual(_ts_string_const(self.src, "MAPPED_LUMPED"), MAPPED_LUMPED)

    def test_mapped_wave(self):
        self.assertEqual(_ts_string_const(self.src, "MAPPED_WAVE"), MAPPED_WAVE)

    def test_mapped_coax(self):
        self.assertEqual(_ts_string_const(self.src, "MAPPED_COAX"), MAPPED_COAX)

    def test_approx_driven_lumped(self):
        self.assertEqual(_ts_string_const(self.src, "APPROX_DRIVEN_LUMPED"), APPROX_DRIVEN_LUMPED)

    def test_approx_planar_microstrip(self):
        self.assertEqual(
            _ts_string_const(self.src, "APPROX_PLANAR_MICROSTRIP"),
            APPROX_PLANAR_MICROSTRIP,
        )

    def test_approx_planar_microstrip_modal(self):
        self.assertEqual(
            _ts_string_const(self.src, "APPROX_PLANAR_MICROSTRIP_MODAL"),
            APPROX_PLANAR_MICROSTRIP_MODAL,
        )

    def test_approx_planar_cpw(self):
        self.assertEqual(_ts_string_const(self.src, "APPROX_PLANAR_CPW"), APPROX_PLANAR_CPW)

    def test_approx_planar_cpw_modal(self):
        self.assertEqual(
            _ts_string_const(self.src, "APPROX_PLANAR_CPW_MODAL"),
            APPROX_PLANAR_CPW_MODAL,
        )

    def test_approx_planar_lumped(self):
        self.assertEqual(
            _ts_string_const(self.src, "APPROX_PLANAR_LUMPED"),
            APPROX_PLANAR_LUMPED,
        )

    def test_approx_coax_tem(self):
        self.assertEqual(_ts_string_const(self.src, "APPROX_COAX_TEM"), APPROX_COAX_TEM)

    def test_ok_line_templates_present_in_ts(self):
        # APPROX_* remain as frozen string literals for Python parity; UI lines use MAPPED_* only.
        self.assertIn(APPROX_DRIVEN_LUMPED, self.src)
        self.assertIn(APPROX_PLANAR_MICROSTRIP, self.src)
        self.assertIn(APPROX_PLANAR_MICROSTRIP_MODAL, self.src)
        self.assertIn(APPROX_PLANAR_CPW, self.src)
        self.assertIn(APPROX_PLANAR_CPW_MODAL, self.src)
        self.assertIn(APPROX_PLANAR_LUMPED, self.src)
        self.assertIn(APPROX_COAX_TEM, self.src)
        self.assertIn(MAPPED_LUMPED, self.src)
        self.assertIn(MAPPED_WAVE, self.src)
        self.assertIn(MAPPED_COAX, self.src)


class PreviewLineFixture(unittest.TestCase):
    def test_expected_lines_use_python_constants(self):
        # Round-trip through JSON so the fixture stays serializable for docs/debug.
        payload = json.loads(json.dumps(EXPECTED_LINES, ensure_ascii=False))
        driven_ok = next(c for c in payload if c["path"] == "driven" and c["ok"])
        planar_ms = next(
            c for c in payload
            if c["path"] == "planar" and c["ok"] and c["ports"][0]["type"] == "microstrip"
            and not c.get("accept")
        )
        planar_ms_modal = next(
            c for c in payload
            if c["path"] == "planar" and c["ok"] and c["ports"][0]["type"] == "microstrip"
            and (c.get("accept") or {}).get("accept_modal_ports") is True
            and (c.get("accept") or {}).get("accept_lumped_terminals") is not True
        )
        planar_ms_both = next(
            c for c in payload
            if c["path"] == "planar" and c["ok"] and c["ports"][0]["type"] == "microstrip"
            and (c.get("accept") or {}).get("accept_modal_ports") is True
            and (c.get("accept") or {}).get("accept_lumped_terminals") is True
        )
        planar_cpw_modal = next(
            c for c in payload
            if c["path"] == "planar" and c["ok"] and c["ports"][0]["type"] == "cpw"
            and (c.get("accept") or {}).get("accept_modal_ports") is True
            and (c.get("accept") or {}).get("accept_lumped_terminals") is not True
        )
        planar_cpw_both = next(
            c for c in payload
            if c["path"] == "planar" and c["ok"] and c["ports"][0]["type"] == "cpw"
            and (c.get("accept") or {}).get("accept_modal_ports") is True
            and (c.get("accept") or {}).get("accept_lumped_terminals") is True
        )
        planar_cpw_lumped = next(
            c for c in payload
            if c["path"] == "planar" and c["ok"] and c["ports"][0]["type"] == "cpw"
            and (c.get("accept") or {}).get("accept_lumped_terminals") is True
            and (c.get("accept") or {}).get("accept_modal_ports") is not True
        )
        planar_lumped = next(
            c for c in payload
            if c["path"] == "planar" and c["ok"] and c["ports"][0]["type"] == "lumped"
        )
        coax_ok = next(c for c in payload if c["path"] == "coax" and c["ok"])
        self.assertEqual(
            driven_ok["lines"][0],
            f"Port 1 · lumped → {MAPPED_LUMPED}",
        )
        self.assertEqual(
            planar_ms["lines"][0],
            f"Port 1 · microstrip → {MAPPED_LUMPED}",
        )
        self.assertEqual(
            planar_ms_modal["lines"][0],
            f"Port 1 · microstrip → {MAPPED_WAVE}",
        )
        self.assertEqual(
            planar_ms_both["lines"][0],
            f"Port 1 · microstrip → {MAPPED_WAVE}",
        )
        self.assertEqual(
            planar_cpw_modal["lines"][0],
            f"Port 1 · cpw → {MAPPED_WAVE}",
        )
        self.assertEqual(
            planar_cpw_both["lines"][0],
            f"Port 1 · cpw → {MAPPED_WAVE}",
        )
        self.assertEqual(
            planar_cpw_lumped["lines"][0],
            f"Port 1 · cpw → {MAPPED_LUMPED}",
        )
        self.assertEqual(
            planar_lumped["lines"][0],
            f"Port 1 · lumped → {MAPPED_LUMPED}",
        )
        self.assertEqual(
            coax_ok["lines"][0],
            f"Port 1 · coaxial → {MAPPED_COAX}",
        )

    def test_reject_phrases(self):
        rejects = [c for c in EXPECTED_LINES if not c["ok"]]
        self.assertTrue(any("does not admit microstrip" in c["lines"][0] for c in rejects))
        self.assertTrue(any("does not admit CPW" in c["lines"][0] for c in rejects))
        self.assertTrue(any("accept_modal_ports required" in c["lines"][0] for c in rejects))
        self.assertTrue(any("not supported on this path" in c["lines"][0] for c in rejects))


if __name__ == "__main__":
    unittest.main()
