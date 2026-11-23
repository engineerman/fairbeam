import { t } from "../i18n/index.ts";

/** Tauri commands may reject with a plain Rust error string instead of a JavaScript Error. */
export function errorText(error: unknown): string {
  if (error instanceof Error && error.name === "IdealWireMeshError") return t("export.mesh.idealWire");
  const raw =
    typeof error === "string" ? error
    : error instanceof Error ? error.message
    : error && typeof error === "object" && "message" in error && typeof error.message === "string" ? error.message
    : null;
  if (raw == null) return String(error);
  // Stale `fairbeam serve` (no hot-reload): e.g. "no route /api/filter-synthesis".
  const noRoute = /^no route (\/api\/[\w./-]+)$/.exec(raw);
  if (noRoute) return t("api.staleServerRoute", { path: noRoute[1] });
  return raw;
}
