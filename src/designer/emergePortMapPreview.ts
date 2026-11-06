/** Client mirror of Stage A emerge_port_map for Run-dialog info lines.
 * Frozen approximation strings must stay identical to Python APPROX_* (parity test).
 */

export const MAPPED_LUMPED = "LumpedPort";

/** Matches python/fairbeam/emerge_port_map.py APPROX_DRIVEN_LUMPED */
export const APPROX_DRIVEN_LUMPED = "finite-width lumped feed plate";

/** Matches python/fairbeam/emerge_port_map.py APPROX_PLANAR_MICROSTRIP */
export const APPROX_PLANAR_MICROSTRIP =
  "microstrip → lumped strip-to-ground terminal; feed_shift/measurement_shift unused";

/** Matches python/fairbeam/emerge_port_map.py APPROX_PLANAR_LUMPED */
export const APPROX_PLANAR_LUMPED = "planar discrete → LumpedPort plate at board-edge face";

export type EmergePortMapPath = "driven" | "planar";

export type PreviewPortInput = {
  number?: number | string;
  type?: string;
  group?: unknown;
};

function portTypes(ports: PreviewPortInput[] | null | undefined): string[] {
  const list = Array.isArray(ports) ? ports : [];
  return list.map((p) => {
    const t = p?.type;
    if (t == null || t === "") return "lumped";
    return String(t);
  });
}

/**
 * Client hint for port-map preview path. Prefer planar when that class can apply
 * (all microstrip or all lumped), matching server admit order; else driven for
 * all-lumped-only would wrongly skip planar Discrete strings — keep planar first.
 */
export function classifyEmergeDraft(ports: PreviewPortInput[] | null | undefined): EmergePortMapPath {
  const types = portTypes(ports);
  if (!types.length) return "planar";
  if (types.every((t) => t === "microstrip")) return "planar";
  if (types.every((t) => t === "lumped")) return "planar";
  // Mixed / unsupported: still planar path so Stage A strings stay valid; admit rejects.
  return "planar";
}

/** Enclosure / air fields: show when planar class is plausible or unsure (plan B3). */
export function draftShowsPlanarEnclosure(ports: PreviewPortInput[] | null | undefined): boolean {
  const types = portTypes(ports);
  if (!types.length) return true;
  return types.every((t) => t === "microstrip" || t === "lumped");
}

/** Driven feed width (+ padding for driven fallback) when all Discrete/lumped. */
export function draftShowsDrivenFeed(ports: PreviewPortInput[] | null | undefined): boolean {
  const types = portTypes(ports);
  return types.length > 0 && types.every((t) => t === "lumped");
}

export function draftNeedsFiniteFeedAccept(ports: PreviewPortInput[] | null | undefined): boolean {
  return draftShowsDrivenFeed(ports);
}

export function draftNeedsLumpedTerminalAccept(ports: PreviewPortInput[] | null | undefined): boolean {
  const types = portTypes(ports);
  return types.length > 0 && types.every((t) => t === "microstrip");
}

export type PreviewPortLine = {
  number: number | string;
  type: string;
  ok: boolean;
  line: string;
};

export type PreviewPortsResult = {
  ok: boolean;
  ports: PreviewPortLine[];
  error?: string;
};

function portType(port: PreviewPortInput): string {
  const t = port.type;
  if (t == null || t === "") return "lumped";
  return String(t);
}

function mapOne(port: PreviewPortInput, path: EmergePortMapPath, index: number): PreviewPortLine {
  const number = port.number ?? index + 1;
  const type = portType(port);
  let ok = false;
  let detail: string;

  if (port.group != null) {
    detail = "port groups not supported";
  } else if (path === "driven" && type === "lumped") {
    ok = true;
    detail = `${MAPPED_LUMPED} (${APPROX_DRIVEN_LUMPED})`;
  } else if (path === "planar" && type === "microstrip") {
    ok = true;
    detail = `${MAPPED_LUMPED} (${APPROX_PLANAR_MICROSTRIP})`;
  } else if (path === "planar" && type === "lumped") {
    ok = true;
    detail = `${MAPPED_LUMPED} (${APPROX_PLANAR_LUMPED})`;
  } else if (path === "driven" && type === "microstrip") {
    detail = "does not admit microstrip";
  } else {
    detail = "not supported on this path";
  }

  return {
    number,
    type,
    ok,
    line: `Port ${number} · ${type} → ${detail}`,
  };
}

/** Preview port→BC lines for the antenna (driven) or planar Run form.
 * Assumes the form will send accept_finite_feed / accept_lumped_terminals as true.
 */
export function previewPorts(
  ports: PreviewPortInput[] | null | undefined,
  path: EmergePortMapPath,
): PreviewPortsResult {
  if (path !== "driven" && path !== "planar") {
    return { ok: false, ports: [], error: `Unknown EMerge port-map path: ${String(path)}` };
  }
  const list = Array.isArray(ports) ? ports : [];
  const lines = list.map((p, i) => mapOne(p ?? {}, path, i));
  return { ok: lines.every((l) => l.ok), ports: lines };
}
