import { t } from "../../i18n";
import topologyCardUrl from "../../assets/hairpin-topology-card.png";
import {
  HAIRPIN_TOPOLOGY_ID,
  hairpinTopology,
  selectHairpinTopology,
  setHairpinStep,
} from "./state";

export default function TopologyStep() {
  return (
    <div class="hd-cards hd-topology" role="listbox" aria-label={t("hairpinDesigner.step.topology")}>
      <button
        type="button"
        class="hd-card hd-card-tall"
        role="option"
        data-topology={HAIRPIN_TOPOLOGY_ID}
        aria-selected={hairpinTopology() === HAIRPIN_TOPOLOGY_ID}
        onClick={() => {
          selectHairpinTopology(HAIRPIN_TOPOLOGY_ID);
          setHairpinStep(2);
        }}
      >
        <img class="hd-card-thumb" src={topologyCardUrl} alt="" />
        <strong class="hd-card-title">{t("hairpinDesigner.topology.hairpin_microstrip_bp")}</strong>
        <span class="hd-card-meta">{t("hairpinDesigner.medium.microstrip")}</span>
      </button>
    </div>
  );
}
