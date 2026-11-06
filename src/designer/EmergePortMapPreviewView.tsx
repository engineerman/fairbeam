import { For, Show } from "solid-js";
import { CircleAlert } from "lucide-solid";
import { t } from "../i18n";
import { draft } from "./store";
import { previewPorts, type EmergePortMapPath } from "./emergePortMapPreview";

/** Informative Stage A port→BC list for experimental EMerge Run forms (no API). */
export default function EmergePortMapPreview(props: { path: EmergePortMapPath }) {
  const preview = () => previewPorts(draft.ports, props.path);
  return (
    <div class="stack" data-testid="emerge-port-map-preview">
      <p class="dz-label">{t("emergePortMap.title")}</p>
      <Show
        when={(draft.ports?.length ?? 0) > 0}
        fallback={<p class="note">{t("emergePortMap.empty")}</p>}
      >
        <ul class="note" style={{ margin: 0, "padding-left": "1.25rem" }}>
          <For each={preview().ports}>{(row) => <li class="mono">{row.line}</li>}</For>
        </ul>
        <Show when={!preview().ok}>
          <p class="status-block status-warn" role="status">
            <CircleAlert size={14} aria-hidden="true" />
            {t("emergePortMap.reject")}
          </p>
        </Show>
      </Show>
    </div>
  );
}
