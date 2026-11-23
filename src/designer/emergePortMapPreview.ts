/** Client mirror of Stage A–C emerge_port_map for Run-dialog info lines.
 * Frozen APPROX_* / MAPPED_* must stay identical to Python (parity test).
 * Preview UI shows short "Port N · type → BC" lines (no APPROX parenthetical).
 */
import { EXPLANATIONS, type Check } from "./checks";

export const MAPPED_LUMPED = "LumpedPort";

/** Matches python/fairbeam/emerge_port_map.py MAPPED_WAVE (parity; shown in UI). */
export const MAPPED_WAVE = "WavePort";

/** Matches python/fairbeam/emerge_port_map.py MAPPED_COAX (parity; shown in UI). */
export const MAPPED_COAX = "CoaxPort";

/** Matches python/fairbeam/emerge_port_map.py APPROX_DRIVEN_LUMPED (parity; not shown in UI). */
export const APPROX_DRIVEN_LUMPED = "finite-width lumped feed plate";

/** Matches python/fairbeam/emerge_port_map.py APPROX_PLANAR_MICROSTRIP (parity; not shown in UI). */
export const APPROX_PLANAR_MICROSTRIP =
  "microstrip → lumped strip-to-ground terminal; feed_shift/measurement_shift unused";

/** Matches python/fairbeam/emerge_port_map.py APPROX_PLANAR_MICROSTRIP_MODAL (parity; not shown in UI). */
export const APPROX_PLANAR_MICROSTRIP_MODAL =
  "microstrip → WavePort at board-edge face; feed_shift/measurement_shift unused";

/** Matches python/fairbeam/emerge_port_map.py APPROX_PLANAR_CPW (parity; not shown in UI). */
export const APPROX_PLANAR_CPW =
  "cpw → lumped gap terminal at board-edge face; feed_shift/measurement_shift unused";

/** Matches python/fairbeam/emerge_port_map.py APPROX_PLANAR_CPW_MODAL (parity; not shown in UI). */
export const APPROX_PLANAR_CPW_MODAL =
  "cpw → WavePort at board-edge CPW aperture; feed_shift/measurement_shift unused";

/** Matches python/fairbeam/emerge_port_map.py APPROX_PLANAR_LUMPED (parity; not shown in UI). */
export const APPROX_PLANAR_LUMPED = "planar discrete → LumpedPort plate at board-edge face";

/** Matches python/fairbeam/emerge_port_map.py APPROX_COAX_TEM (parity; not shown in UI). */
export const APPROX_COAX_TEM = "Design coaxial → analytic CoaxPort TEM; constant εr fill";

export type EmergePortMapPath = "driven" | "planar" | "coax";

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
 * Client hint for port-map preview path. Prefer coax when all coaxial; else planar
 * when that class can apply (all microstrip, all CPW, or all lumped), matching server admit order.
 */
export function classifyEmergeDraft(ports: PreviewPortInput[] | null | undefined): EmergePortMapPath {
  const types = portTypes(ports);
  if (!types.length) return "planar";
  if (types.every((t) => t === "coaxial")) return "coax";
  if (types.every((t) => t === "microstrip")) return "planar";
  if (types.every((t) => t === "cpw")) return "planar";
  if (types.every((t) => t === "lumped")) return "planar";
  // Mixed / unsupported: still planar path so Stage A strings stay valid; admit rejects.
  return "planar";
}

/** Enclosure / air fields: show when planar class is plausible or unsure (plan B3). */
export function draftShowsPlanarEnclosure(ports: PreviewPortInput[] | null | undefined): boolean {
  const types = portTypes(ports);
  if (!types.length) return true;
  if (types.every((t) => t === "coaxial")) return false;
  return types.every((t) => t === "microstrip" || t === "cpw" || t === "lumped");
}

/** Driven feed width (+ padding for driven fallback) when all Discrete/lumped. */
export function draftShowsDrivenFeed(ports: PreviewPortInput[] | null | undefined): boolean {
  const types = portTypes(ports);
  return types.length > 0 && types.every((t) => t === "lumped");
}

/** Domain padding for all-coaxial Stage B path (reuses padding_mm). */
export function draftShowsCoaxPadding(ports: PreviewPortInput[] | null | undefined): boolean {
  const types = portTypes(ports);
  return types.length > 0 && types.every((t) => t === "coaxial");
}

export function draftNeedsFiniteFeedAccept(ports: PreviewPortInput[] | null | undefined): boolean {
  return draftShowsDrivenFeed(ports);
}

export function draftNeedsLumpedTerminalAccept(ports: PreviewPortInput[] | null | undefined): boolean {
  const types = portTypes(ports);
  // Microstrip strip-to-ground or classic CPW coplanar-gap plate (server accept_lumped_terminals).
  return types.length > 0
    && (types.every((t) => t === "microstrip") || types.every((t) => t === "cpw"));
}

/** Stage C modal WavePort opt-in for all-microstrip or all-cpw planar Designs. */
export function draftNeedsModalPortAccept(ports: PreviewPortInput[] | null | undefined): boolean {
  const types = portTypes(ports);
  if (!types.length) return false;
  return types.every((t) => t === "microstrip") || types.every((t) => t === "cpw");
}

export function draftNeedsCoaxialTemAccept(ports: PreviewPortInput[] | null | undefined): boolean {
  return draftShowsCoaxPadding(ports);
}

/** Run-form accept intent for planar microstrip preview (modal wins when both). */
export type PreviewAcceptIntent = {
  accept_modal_ports?: boolean;
  accept_lumped_terminals?: boolean;
};

/** UI map choice for Port mapping to EMerge (global accept flags underneath). */
export type EmergeMapKind = "lumped" | "wave" | "coax";

export type EmergeMapOption = {
  kind: EmergeMapKind;
  /** Shown mapped BC name (MAPPED_*). */
  mapped: string;
  /** i18n key for tooltip honesty copy. */
  tipKey: string;
};

/** Admitted EMerge map options for one Design port on this path (empty = unsupported). */
export function mapOptionsFor(type: string, path: EmergePortMapPath): EmergeMapOption[] {
  if (path === "coax" && type === "coaxial") {
    return [{ kind: "coax", mapped: MAPPED_COAX, tipKey: "emergeExp.acceptCoax" }];
  }
  if (path === "driven" && type === "lumped") {
    return [{ kind: "lumped", mapped: MAPPED_LUMPED, tipKey: "emergeExp.acceptFinite" }];
  }
  if (path === "planar" && type === "microstrip") {
    return [
      { kind: "lumped", mapped: MAPPED_LUMPED, tipKey: "emergeExp.acceptLumped" },
      { kind: "wave", mapped: MAPPED_WAVE, tipKey: "emergeExp.acceptModal" },
    ];
  }
  if (path === "planar" && type === "cpw") {
    return [
      { kind: "lumped", mapped: MAPPED_LUMPED, tipKey: "emergeExp.acceptLumped" },
      { kind: "wave", mapped: MAPPED_WAVE, tipKey: "emergeExp.acceptModal" },
    ];
  }
  if (path === "planar" && type === "lumped") {
    return [{ kind: "lumped", mapped: MAPPED_LUMPED, tipKey: "emergeExp.acceptFinite" }];
  }
  return [];
}

/** Default map kind for the draft: prefer Lumped when both Lumped and Wave exist. */
export function defaultMapKind(
  ports: PreviewPortInput[] | null | undefined,
  path: EmergePortMapPath,
): EmergeMapKind | null {
  const list = Array.isArray(ports) ? ports : [];
  if (!list.length) return null;
  const opts = mapOptionsFor(portType(list[0] ?? {}), path);
  if (!opts.length) return null;
  if (opts.some((o) => o.kind === "lumped")) return "lumped";
  return opts[0]!.kind;
}

/** Preview accept flags from exclusive UI map kind (modal wins only when kind is wave). */
export function acceptIntentFromMapKind(kind: EmergeMapKind | null): PreviewAcceptIntent {
  if (kind === "wave") return { accept_modal_ports: true };
  if (kind === "lumped") return { accept_lumped_terminals: true };
  return {};
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

function mapOne(
  port: PreviewPortInput,
  path: EmergePortMapPath,
  index: number,
  accept?: PreviewAcceptIntent,
): PreviewPortLine {
  const number = port.number ?? index + 1;
  const type = portType(port);
  let ok = false;
  let detail: string;

  if (port.group != null) {
    detail = "port groups not supported";
  } else if (path === "driven" && type === "lumped") {
    ok = true;
    // Short UI line only; APPROX_* stay exported for Python parity, not shown here.
    detail = MAPPED_LUMPED;
  } else if (path === "planar" && type === "microstrip") {
    ok = true;
    // Mirror server: accept_modal_ports wins over lumped when both are set.
    detail = accept?.accept_modal_ports ? MAPPED_WAVE : MAPPED_LUMPED;
  } else if (path === "planar" && type === "cpw") {
    // Mirror server: modal → WavePort; lumped accept → LumpedPort; else reject.
    if (accept?.accept_modal_ports) {
      ok = true;
      detail = MAPPED_WAVE;
    } else if (accept?.accept_lumped_terminals) {
      ok = true;
      detail = MAPPED_LUMPED;
    } else {
      detail = "accept_modal_ports required";
    }
  } else if (path === "planar" && type === "lumped") {
    ok = true;
    detail = MAPPED_LUMPED;
  } else if (path === "coax" && type === "coaxial") {
    ok = true;
    detail = MAPPED_COAX;
  } else if (path === "driven" && type === "microstrip") {
    detail = "does not admit microstrip";
  } else if (path === "driven" && type === "cpw") {
    detail = "does not admit CPW";
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

/** Preview port→BC lines for the antenna (driven), planar, or coax Run form.
 * Pass accept intent so planar microstrip/CPW show WavePort when modal wins.
 */
export function previewPorts(
  ports: PreviewPortInput[] | null | undefined,
  path: EmergePortMapPath,
  accept?: PreviewAcceptIntent,
): PreviewPortsResult {
  if (path !== "driven" && path !== "planar" && path !== "coax") {
    return { ok: false, ports: [], error: `Unknown EMerge port-map path: ${String(path)}` };
  }
  const list = Array.isArray(ports) ? ports : [];
  const lines = list.map((p, i) => mapOne(p ?? {}, path, i, accept));
  return { ok: lines.every((l) => l.ok), ports: lines };
}

/** Plain-English Checks copy (must match checks.msg.emerge-port-admit.* in en.json for i18n). */
function emergePortCheckMessage(number: number | string, type: string): string {
  if (type === "waveguide") {
    return `Port ${number}: waveguide ports only work with openEMS, not EMerge experimental`;
  }
  if (type === "coaxial") {
    return `Port ${number}: coaxial ports work with EMerge only when every port in the design is coaxial`;
  }
  return `Port ${number}: ${type} ports are outside what EMerge experimental can simulate on a Design`;
}

/** Live Checks while EMerge is the active engine (mirrors emerge_solver.admit port rules). */
export function emergeAdmitChecks(ports: PreviewPortInput[] | null | undefined): Check[] {
  const list = Array.isArray(ports) ? ports : [];
  if (!list.length) return [];
  const types = portTypes(ports);
  const unique = [...new Set(types)];
  const explain = EXPLANATIONS["emerge-port-admit"];
  if (unique.length > 1) {
    return [{
      severity: "error",
      path: "ports",
      code: "emerge-port-admit",
      message: `Ports in this design use different types (${unique.sort().join(", ")}). EMerge experimental requires every port to be the same type, or switch to openEMS`,
      explain,
    }];
  }
  const path = classifyEmergeDraft(ports);
  const kind = defaultMapKind(ports, path);
  const preview = previewPorts(ports, path, acceptIntentFromMapKind(kind));
  if (preview.ok) return [];
  const out: Check[] = [];
  preview.ports.forEach((row, i) => {
    if (row.ok) return;
    out.push({
      severity: "error",
      path: `ports[${i}]`,
      code: "emerge-port-admit",
      message: emergePortCheckMessage(row.number, row.type),
      explain,
    });
  });
  if (!out.length) {
    out.push({
      severity: "error",
      path: "ports",
      code: "emerge-port-admit",
      message: "At least one port in this design cannot run with EMerge experimental",
      explain,
    });
  }
  return out;
}
