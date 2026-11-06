"""Unit tests for EMerge exterior surface wireframe packing (no native EMerge import)."""
from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "fairbeam_emerge_worker.py"
ADAPTER = ROOT / "fairbeam_emerge.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PackSurfaceEdges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker = _load(WORKER, "fairbeam_emerge_worker_surface")

    def test_pack_metres_to_mm_and_remap(self):
        nodes = np.array([[0.0, 0.01, 0.02], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=float)
        edges = np.array([[0, 1], [1, 2]], dtype=np.int64).T
        surface = self.worker.pack_surface_edges(nodes, edges)
        self.assertEqual(surface["schema"], self.worker.MESH_SURFACE_SCHEMA)
        self.assertEqual(surface["units"], "mm")
        self.assertEqual(surface["nodes_mm"], [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [20.0, 0.0, 0.0]])
        self.assertEqual(surface["edges"], [[0, 1], [1, 2]])
        self.assertFalse(surface["thinned"])
        self.assertEqual(surface["edge_stride"], 1)
        self.assertEqual(surface["edge_count"], 2)

    def test_pack_thins_when_over_cap(self):
        n = 9
        nodes = np.vstack([np.linspace(0, 1, n), np.zeros(n), np.zeros(n)])
        edges = np.array([[i, i + 1] for i in range(n - 1)], dtype=np.int64).T
        surface = self.worker.pack_surface_edges(nodes, edges, max_edges=3)
        self.assertTrue(surface["thinned"])
        self.assertGreaterEqual(surface["edge_stride"], 2)
        self.assertLessEqual(len(surface["edges"]), 3)
        self.assertTrue(all(math.isfinite(c) for p in surface["nodes_mm"] for c in p))


class AssessMeshSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fem = _load(ADAPTER, "fairbeam_emerge_surface")

    def test_assess_mesh_keeps_surface(self):
        surface = {
            "schema": self.fem.MESH_SURFACE_SCHEMA,
            "units": "mm",
            "nodes_mm": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            "edges": [[0, 1]],
            "thinned": False,
            "edge_stride": 1,
            "edge_count": 1,
        }
        raw = {"mesh_only": True, "kind": "design", "emerge_version": "3.0.0b12",
               "elapsed_seconds": 0.5,
               "mesh": {"nodes": 10, "tetrahedra": 20, "surface": surface}}
        case = {"kind": "design", "resolution": 0.25}
        result = self.fem.assess_mesh(raw, case)
        self.assertEqual(result["status"], "mesh_exported")
        self.assertEqual(result["mesh"]["surface"]["edges"], [[0, 1]])
        self.assertIn("overlay", " ".join(result["limitations"]).lower())


if __name__ == "__main__":
    unittest.main()
