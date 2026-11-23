// Pure checks for the hairpin wizard state helpers (no browser).
import fs from "node:fs";

const state = fs.readFileSync(new URL("../src/designer/hairpinDesigner/state.ts", import.meta.url), "utf8");

if (!state.includes('HAIRPIN_STEP_KEYS = ["topology", "parameters", "preview"]')) {
  throw new Error("step keys");
}
if (!/HAIRPIN_INTRA_GAP_MM\s*=\s*2/.test(state)) throw new Error("intra gap const");

const defaultsAt = state.indexOf("export const HAIRPIN_FORM_DEFAULTS");
if (defaultsAt < 0) throw new Error("form defaults missing");
const defaultsBlock = state.slice(defaultsAt, state.indexOf("};", defaultsAt));
if (/intra_gap_mm/.test(defaultsBlock)) throw new Error("intra_gap still on form defaults");

const formAt = state.indexOf("export interface HairpinParameterForm");
if (formAt < 0) throw new Error("form interface missing");
const formBlock = state.slice(formAt, state.indexOf("}", formAt));
if (/intra_gap_mm/.test(formBlock)) throw new Error("intra_gap still on form");
if (/feed_len|board_margin/.test(formBlock)) throw new Error("layout fields still on form");
if (!/HAIRPIN_FEED_LEN_MM\s*=\s*6/.test(state)) throw new Error("feed length const");
if (!/HAIRPIN_BOARD_MARGIN_MM\s*=\s*8/.test(state)) throw new Error("board margin const");
if (!/feed_len_mm:\s*HAIRPIN_FEED_LEN_MM/.test(state)) throw new Error("request feed length");
if (!/board_margin_mm:\s*HAIRPIN_BOARD_MARGIN_MM/.test(state)) throw new Error("request board margin");

if (!/intra_gap_mm:\s*HAIRPIN_INTRA_GAP_MM/.test(state)) {
  throw new Error("request must send HAIRPIN_INTRA_GAP_MM");
}
if (!state.includes("export function hairpinCanFinish")) throw new Error("hairpinCanFinish");
if (!state.includes("export function hairpinSelectClosedForm")) throw new Error("hairpinSelectClosedForm");
if (!state.includes("export function hairpinSelectEdc")) throw new Error("hairpinSelectEdc");
if (!state.includes("export async function hairpinStartEdc")) throw new Error("hairpinStartEdc");
if (!state.includes("export async function hairpinFinish")) throw new Error("hairpinFinish");
const solveStep = fs.readFileSync(new URL("../src/designer/hairpinDesigner/SolveStep.tsx", import.meta.url), "utf8");
if (!solveStep.includes("hairpinStartEdc")) throw new Error("SolveStep must call hairpinStartEdc");
if (!solveStep.includes("hairpinDesigner.solve.startEdc")) throw new Error("Start EDC label");
if (state.includes("setHairpinStep(4)")) throw new Error("step 4 still assigned");
if (!state.includes("setHairpinHighlightKey")) throw new Error("highlight key");
if (!state.includes("HairpinEdcStudy")) throw new Error("edc study type");

const api = fs.readFileSync(new URL("../src/runner/api.ts", import.meta.url), "utf8");
if (!api.includes('phase?: "qe" | "k" | "assemble" | null')) throw new Error("edc phase");

const table = fs.readFileSync(new URL("../src/designer/hairpinDesigner/DimensionTable.tsx", import.meta.url), "utf8");
for (const key of ["q_len", "w_feed", "tap_from_fold", "feed_len", "board_margin"]) {
  if (!table.includes(key)) throw new Error(`table key ${key}`);
}
if (!table.includes("w\\d+") || !table.includes("gap\\d+") || !table.includes("sp\\d+")) {
  throw new Error("table indexed keys");
}
if (!table.includes("hd-dim-row-active")) throw new Error("table highlight class");

const geometry = fs.readFileSync(new URL("../src/designer/hairpinDesigner/GeometryStep.tsx", import.meta.url), "utf8");
if (!geometry.includes("setHairpinHighlightKey")) throw new Error("geometry highlight");
if (geometry.includes("hd-pin::before") || /::before/.test(geometry)) throw new Error("geometry still paints dots");

const css = fs.readFileSync(new URL("../src/styles/hairpin-designer.css", import.meta.url), "utf8");
if (/hd-pin::before/.test(css)) throw new Error("pin dots still in css");
if (!css.includes("hd-pin-active")) throw new Error("pin active class");

const stack = fs.readFileSync(new URL("../src/designer/hairpinDesigner/StackUpDiagram.tsx", import.meta.url), "utf8");
if (!stack.includes('StackUpKind = "microstrip" | "stripline"') && !stack.includes('"microstrip" | "stripline"')) {
  throw new Error("StackUpDiagram must support microstrip | stripline");
}
if (!stack.includes("ariaStripline")) throw new Error("stripline stack aria key");
if (!/topGroundY|bottomGroundY/.test(stack)) throw new Error("stripline must draw top and bottom grounds");
const params = fs.readFileSync(new URL("../src/designer/hairpinDesigner/ParametersStep.tsx", import.meta.url), "utf8");
if (!params.includes("HAIRPIN_STRIPLINE_TOPOLOGY_ID")) throw new Error("ParametersStep must pick stack kind from topology");
if (!params.includes('kind={hairpinTopology() === HAIRPIN_STRIPLINE_TOPOLOGY_ID ? "stripline" : "microstrip"}')) {
  throw new Error("ParametersStep must pass stripline kind for stripline topology");
}
const en = fs.readFileSync(new URL("../src/i18n/en.json", import.meta.url), "utf8");
const tr = fs.readFileSync(new URL("../src/i18n/tr.json", import.meta.url), "utf8");
if (!en.includes('"hairpinDesigner.stack.ariaStripline"')) throw new Error("en ariaStripline");
if (!tr.includes('"hairpinDesigner.stack.ariaStripline"')) throw new Error("tr ariaStripline");

console.log("check-hairpin-wizard: ok");
