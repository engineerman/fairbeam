// The colour bar of the field-plane map shown in the 3D view (scene/fieldPlanes.ts), with its Magnitude
// / Phase / Animate, component and dB / linear controls (FieldPlaneControls.tsx, shared with the 2D
// field-map tab). It sits in the viewport's colour-scale column next to the pattern and current bars.
// When the run has several field_planes, a Map dropdown matches the Field map tab (same labels).
import { createMemo, For, Show } from "solid-js";
import { designResult } from "../runner/designRun";
import { bundle, fieldPlaneMap } from "../state";
import { modelToMm } from "../lib/modelUnits";
import { fieldPlaneLabel } from "../designer/navModel";
import { focusResult, resultFocus } from "../designer/resultFocus";
import { fieldPlaneValues } from "./fieldPlaneModel";
import { currentFieldPlaneView, FieldPlaneControls, FieldPlaneLegend, valueLabel } from "./FieldPlaneControls";
import { t } from "../i18n";

export default function FieldPlaneScale() {
  const maps = () => bundle()?.field_planes ?? [];
  const index = () => fieldPlaneMap();
  const shown = () => {
    const i = index();
    return i === null ? undefined : maps()[i];
  };
  const pick = (k: number) => {
    const list = maps();
    const file = resultFocus()?.file ?? designResult()?.file;
    if (file && list[k]) focusResult({ file, view: "fieldplane", f: list[k].f, map: k });
  };
  return (
    <Show when={shown()}>
      {(m) => {
        const heading = createMemo(() => {
          const v = currentFieldPlaneView(false);
          return valueLabel(m(), fieldPlaneValues(m(), v), v.scale);
        });
        const mm = () => modelToMm(bundle());
        return (
          <div class="colorbar" role="group" aria-label={t("viewport.fieldPlane.aria", { label: fieldPlaneLabel(m(), mm()) })} data-field-plane>
            <Show when={maps().length > 1}>
              <label class="fm-field"><span>{t("fieldMap.map")}</span>
                <select class="btn btn-ghost btn-sm" onChange={(e) => pick(Number(e.currentTarget.value))}>
                  <For each={maps()}>{(map, k) =>
                    <option value={k()} selected={k() === index()}>{fieldPlaneLabel(map, mm())}</option>
                  }</For>
                </select>
              </label>
            </Show>
            <div class="colorbar-title">{fieldPlaneLabel(m(), mm())}</div>
            <Show when={m().port !== undefined}>
              <div class="colorbar-port">{t("viewport.fieldPlane.portDriven", { port: m().port })}</div>
            </Show>
            <FieldPlaneControls map={m()} />
            <FieldPlaneLegend map={m()} />
            <div class="colorbar-unit">
              {heading()}
              {m().unit === "arb." ? "" : `, ${t("viewport.fieldPlane.incident")}`}
            </div>
          </div>
        );
      }}
    </Show>
  );
}
