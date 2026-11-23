import { For, createEffect } from "solid-js";
import { t } from "../../i18n";
import { dimText } from "../../drawing/svg.ts";
import type { Design, DesignParam } from "../types.ts";
import { hairpinHighlightKey, hairpinSynthesis, setHairpinHighlightKey } from "./state.ts";
import type { FilterSynthesisResponse } from "./synthesisTypes.ts";

/** Independent layout knobs shown in the preview table and on the 3D labels. */
const LAYOUT_KEY = /^(?:q_len|w_feed|tap_from_fold|feed_len|board_margin|w\d+|gap\d+|sp\d+)$/;

export interface HairpinDimensionRow {
  key: string;
  value: number;
  unit: string;
  label: string;
}

function rank(key: string): number {
  if (key === "q_len") return 0;
  if (key === "w_feed") return 1;
  if (key === "tap_from_fold") return 2;
  const width = /^w(\d+)$/.exec(key);
  if (width) return 100 + Number(width[1]);
  const gap = /^gap(\d+)$/.exec(key);
  if (gap) return 200 + Number(gap[1]);
  const spacing = /^sp(\d+)$/.exec(key);
  if (spacing) return 300 + Number(spacing[1]);
  if (key === "feed_len") return 400;
  if (key === "board_margin") return 401;
  return 900;
}

function independentLayout(param: DesignParam): boolean {
  return param.expr === undefined && typeof param.default === "number" && Number.isFinite(param.default) && LAYOUT_KEY.test(param.key);
}

/** Rows from the design's numeric layout params, with synthesis `dimensions` filling labels or missing keys. */
export function hairpinDimensionRows(
  design: Design | null | undefined,
  dimensions?: FilterSynthesisResponse["dimensions"],
): HairpinDimensionRow[] {
  const extras = new Map((dimensions ?? []).filter((row) => LAYOUT_KEY.test(row.key)).map((row) => [row.key, row]));
  const rows: HairpinDimensionRow[] = [];
  const seen = new Set<string>();
  for (const param of design?.params ?? []) {
    if (!independentLayout(param)) continue;
    const extra = extras.get(param.key);
    seen.add(param.key);
    rows.push({
      key: param.key,
      value: param.default as number,
      unit: extra?.unit || param.unit || "mm",
      label: extra?.label || param.label || param.key,
    });
  }
  for (const extra of extras.values()) {
    if (seen.has(extra.key) || typeof extra.value !== "number" || !Number.isFinite(extra.value)) continue;
    rows.push({
      key: extra.key,
      value: extra.value,
      unit: extra.unit || "mm",
      label: extra.label || extra.key,
    });
  }
  rows.sort((a, b) => rank(a.key) - rank(b.key) || a.key.localeCompare(b.key));
  return rows;
}

function leaveParam(key: string, event: PointerEvent) {
  const next = event.relatedTarget;
  if (next instanceof Element && next.closest(`[data-dim="${CSS.escape(key)}"]`)) return;
  setHairpinHighlightKey((current) => (current === key ? null : current));
}

function DimCells(props: { row: HairpinDimensionRow }) {
  const active = () => props.row.key === hairpinHighlightKey();
  return (
    <>
      <th
        scope="row"
        data-dim={props.row.key}
        classList={{ "hd-dim-row-active": active() }}
        onPointerEnter={() => setHairpinHighlightKey(props.row.key)}
        onPointerLeave={(event) => leaveParam(props.row.key, event)}
      >{props.row.key}</th>
      <td
        data-dim={props.row.key}
        classList={{ "hd-dim-row-active": active() }}
        onPointerEnter={() => setHairpinHighlightKey(props.row.key)}
        onPointerLeave={(event) => leaveParam(props.row.key, event)}
      >{dimText(props.row.value)} {props.row.unit}</td>
    </>
  );
}

export default function DimensionTable() {
  let scroller: HTMLDivElement | undefined;
  const rows = () => hairpinDimensionRows(hairpinSynthesis()?.design, hairpinSynthesis()?.dimensions);
  const pairs = () => {
    const list = rows();
    const out: Array<[HairpinDimensionRow, HairpinDimensionRow | null]> = [];
    for (let i = 0; i < list.length; i += 2) out.push([list[i], list[i + 1] ?? null]);
    return out;
  };
  createEffect(() => {
    const key = hairpinHighlightKey();
    const box = scroller;
    if (!key || !box) return;
    const cell = box.querySelector<HTMLElement>(`[data-dim="${CSS.escape(key)}"]`);
    const row = cell?.closest("tr");
    if (!row) return;
    const rowBox = row.getBoundingClientRect();
    const view = box.getBoundingClientRect();
    if (rowBox.top < view.top) box.scrollTop -= view.top - rowBox.top;
    else if (rowBox.bottom > view.bottom) box.scrollTop += rowBox.bottom - view.bottom;
  });
  return (
    <section class="hd-dim-table" aria-label={t("hairpinDesigner.table.title")}>
      <h3>{t("hairpinDesigner.table.title")}</h3>
      <div class="hd-dim-scroll" ref={scroller}>
        <table>
          <colgroup>
            <col class="hd-dim-key" />
            <col class="hd-dim-value" />
            <col class="hd-dim-key" />
            <col class="hd-dim-value" />
          </colgroup>
          <tbody>
            <For each={pairs()}>
              {(pair) => (
                <tr>
                  <DimCells row={pair[0]} />
                  {pair[1] ? <DimCells row={pair[1]} /> : <><th /><td /></>}
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>
    </section>
  );
}
