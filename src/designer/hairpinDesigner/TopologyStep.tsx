import { For } from "solid-js";
import { t } from "../../i18n";
import topologyCardUrl from "../../assets/hairpin-topology-card.png";
import {
  HAIRPIN_MITERED_TOPOLOGY_ID,
  HAIRPIN_TOPOLOGY_ID,
  HAIRPIN_TOPOLOGY_IDS,
  type HairpinTopologyId,
  hairpinTopology,
  selectHairpinTopology,
  setHairpinStep,
} from "./state";

const TOPOLOGY_TITLE_KEY: Record<HairpinTopologyId, string> = {
  [HAIRPIN_TOPOLOGY_ID]: "hairpinDesigner.topology.hairpin_microstrip_bp",
  [HAIRPIN_MITERED_TOPOLOGY_ID]: "hairpinDesigner.topology.hairpin_microstrip_bp_mitered",
};

/**
 * Per-card thumbnails. Square uses the shipped asset.
 * Mitered: drop user art at `src/assets/hairpin-topology-card-mitered.png`, then
 * `import topologyCardMiteredUrl from "../../assets/hairpin-topology-card-mitered.png"`
 * and point `[HAIRPIN_MITERED_TOPOLOGY_ID]` at it (placeholder shares the square thumb until then).
 */
const TOPOLOGY_THUMB_URL: Record<HairpinTopologyId, string> = {
  [HAIRPIN_TOPOLOGY_ID]: topologyCardUrl,
  [HAIRPIN_MITERED_TOPOLOGY_ID]: topologyCardUrl,
};

export default function TopologyStep() {
  return (
    <div class="hd-cards hd-topology" role="listbox" aria-label={t("hairpinDesigner.step.topology")}>
      <For each={[...HAIRPIN_TOPOLOGY_IDS]}>
        {(id) => (
          <button
            type="button"
            class="hd-card hd-card-tall"
            role="option"
            data-topology={id}
            aria-selected={hairpinTopology() === id}
            onClick={() => {
              selectHairpinTopology(id);
              setHairpinStep(2);
            }}
          >
            <img class="hd-card-thumb" src={TOPOLOGY_THUMB_URL[id]} alt="" />
            <strong class="hd-card-title">{t(TOPOLOGY_TITLE_KEY[id])}</strong>
            <span class="hd-card-meta">{t("hairpinDesigner.medium.microstrip")}</span>
          </button>
        )}
      </For>
    </div>
  );
}
