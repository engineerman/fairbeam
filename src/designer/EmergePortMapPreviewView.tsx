import { For, Show } from "solid-js";
import { CircleAlert } from "lucide-solid";
import { t } from "../i18n";
import { draft } from "./store";
import {
  acceptIntentFromMapKind,
  mapOptionsFor,
  previewPorts,
  type EmergeMapKind,
  type EmergePortMapPath,
} from "./emergePortMapPreview";

/** Informative Stage A–C port→BC list for experimental EMerge Run forms (no API). */
export default function EmergePortMapPreview(props: {
  path: EmergePortMapPath;
  mapKind: EmergeMapKind | null;
  onMapKind: (kind: EmergeMapKind) => void;
}) {
  const accept = () => acceptIntentFromMapKind(props.mapKind);
  const preview = () => previewPorts(draft.ports, props.path, accept());
  const unsupportedHint = (number: number | string, type: string) => {
    const n = String(number);
    if (type === "waveguide") return t("checks.msg.emerge-port-admit.waveguide", { number: n });
    if (type === "coaxial") return t("checks.msg.emerge-port-admit.coaxial", { number: n });
    return t("checks.msg.emerge-port-admit.unsupported", { number: n, type });
  };
  return (
    <div class="stack" data-testid="emerge-port-map-preview">
      <p class="dz-label">{t("emergePortMap.title")}</p>
      <p class="note">{t("emergePortMap.intro")}</p>
      <Show
        when={(draft.ports?.length ?? 0) > 0}
        fallback={<p class="note">{t("emergePortMap.empty")}</p>}
      >
        <ul class="note" style={{ margin: 0, padding: 0, "list-style": "none" }}>
          <For each={preview().ports}>{(row, index) => {
            const type = row.type;
            const opts = () => mapOptionsFor(type, props.path);
            const tip = () => {
              const o = opts().find((x) => x.kind === props.mapKind) ?? opts()[0];
              return o ? t(o.tipKey) : "";
            };
            return (
              <li class="cluster" style={{
                "flex-wrap": "nowrap",
                "align-items": "center",
                gap: "0.5rem",
                "white-space": "nowrap",
              }}>
                <span class="mono">{`Port ${row.number} · ${type}`}</span>
                <Show when={opts().length > 1} fallback={
                  <Show when={opts().length === 1}>
                    <span class="mono" title={tip()} data-testid="emerge-port-map-label">
                      → {opts()[0]!.mapped}
                    </span>
                  </Show>
                }>
                  <span aria-hidden="true">→</span>
                  <select
                    class="rp-select rp-select-sm mono"
                    data-testid={index() === 0 ? "emerge-port-map-kind" : undefined}
                    aria-label={t("emergePortMap.mapLabel", { number: String(row.number) })}
                    title={tip()}
                    value={props.mapKind ?? opts()[0]!.kind}
                    onChange={(e) => props.onMapKind(e.currentTarget.value as EmergeMapKind)}
                  >
                    <For each={opts()}>{(o) =>
                      <option value={o.kind} title={t(o.tipKey)}>{o.mapped}</option>
                    }</For>
                  </select>
                </Show>
                <Show when={!row.ok && opts().length === 0}>
                  <span>{unsupportedHint(row.number, type)}</span>
                </Show>
              </li>
            );
          }}</For>
        </ul>
        <Show when={!preview().ok}>
          <p class="status-block status-critical" role="alert" data-testid="emerge-port-map-reject">
            <CircleAlert size={14} aria-hidden="true" />
            {t("emergePortMap.reject")}
          </p>
        </Show>
      </Show>
    </div>
  );
}
