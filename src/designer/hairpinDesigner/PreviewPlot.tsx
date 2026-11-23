import { createMemo, Show } from "solid-js";
import LineChart, { type Series } from "../../charts/LineChart";
import { t } from "../../i18n";
import { hairpinLivePreview } from "./state";

/** Fixed magnitude axis. Samples below the floor are omitted. */
const DB_FLOOR = -75;
const Y_DOMAIN: [number, number] = [DB_FLOOR, 0];

function aboveFloor(y: number[]): number[] {
  return y.map((v) => (Number.isFinite(v) && v >= DB_FLOOR ? v : NaN));
}

/** Ideal |S11| / |S21| from the synthesizer preview. Not an openEMS result. */
export default function PreviewPlot() {
  const series = createMemo<Series[]>(() => {
    const preview = hairpinLivePreview();
    if (!preview?.f_hz.length) return [];
    const x = preview.f_hz.map((hz) => hz / 1e9);
    return [
      { id: "s11", label: "S11", color: "--al-series-1", x, y: aboveFloor(preview.s11_db) },
      { id: "s21", label: "S21", color: "--al-series-2", x, y: aboveFloor(preview.s21_db) },
    ];
  });
  return (
    <figure class="hd-preview-plot">
      <div class="hd-preview-chart">
        <Show when={series().length > 0}>
          <LineChart
            series={series()}
            xLabel={t("chart.frequencyGHz")}
            yLabel={t("research.magnitude")}
            yDomain={Y_DOMAIN}
            yTickValues={[-75, -50, -25, 0]}
            ariaLabel={t("hairpinDesigner.preview.sCaption")}
          />
        </Show>
      </div>
      <figcaption class="hd-preview-caption">{t("hairpinDesigner.preview.sCaption")}</figcaption>
    </figure>
  );
}
