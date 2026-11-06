import { createSignal } from "solid-js";
import { bundle } from "../state";
import type { Bundle } from "../types";

/** Exterior FEM surface edges for Mesh view under EMerge (never FDTD planes). */
export type EmergeFemSurface = {
  schema?: string;
  units: "mm";
  nodes_mm: number[][];
  edges: number[][];
  thinned?: boolean;
  edge_stride?: number;
  edge_count?: number;
};

export type EmergeFemOverlay = {
  nodes: number;
  tetrahedra: number;
  surface: EmergeFemSurface;
  /** Session mesh-only generate; cleared when the design identity changes. */
  source?: "session" | "bundle";
};

const [sessionFemMesh, setSessionFemMeshRaw] = createSignal<EmergeFemOverlay | null>(null);

export { sessionFemMesh };

export function setSessionFemMesh(overlay: EmergeFemOverlay | null): void {
  setSessionFemMeshRaw(overlay);
}

export function clearSessionFemMesh(): void {
  setSessionFemMeshRaw(null);
}

export function femOverlayFromBundle(b: Bundle | null | undefined): EmergeFemOverlay | null {
  const fem = b?.mesh?.fem;
  if (!fem?.surface || !Array.isArray(fem.surface.nodes_mm) || !Array.isArray(fem.surface.edges)) {
    return null;
  }
  if (fem.surface.units !== "mm") return null;
  return {
    nodes: Number(fem.nodes) || 0,
    tetrahedra: Number(fem.tetrahedra) || 0,
    surface: fem.surface,
    source: "bundle",
  };
}

/** Active overlay for Mesh view: session generate wins, else focused EMerge result bundle. */
export function emergeFemOverlay(): EmergeFemOverlay | null {
  return sessionFemMesh() ?? femOverlayFromBundle(bundle());
}

export function hasEmergeFemOverlay(): boolean {
  const o = emergeFemOverlay();
  return !!o && o.surface.edges.length > 0 && o.surface.nodes_mm.length > 0;
}
