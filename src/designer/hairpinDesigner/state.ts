import { createSignal } from "solid-js";
import { t } from "../../i18n";
import { confirmDraftDiscard } from "../../lib/ConfirmDialog";
import { freeDesignId } from "../../lib/designId";
import { errorText } from "../../lib/errorText";
import { showToast } from "../../lib/toast";
import { api, type HairpinEdcStudy } from "../../runner/api";
import { models, refreshModels } from "../../runner/store";
import type { FilterSynthesisPreview, FilterSynthesisRequest, FilterSynthesisResponse } from "./synthesisTypes";
import type { Design } from "../types";
import { createDesign, openDesign } from "../store";

/** Square-fold hairpin (legacy default). */
export const HAIRPIN_TOPOLOGY_ID = "hairpin_microstrip_bp" as const;
/** Douville–James mitered outer folds (engineerman/fairbeam#2). */
export const HAIRPIN_MITERED_TOPOLOGY_ID = "hairpin_microstrip_bp_mitered" as const;
/** Stripline sandwich hairpin (engineerman/fairbeam#4). */
export const HAIRPIN_STRIPLINE_TOPOLOGY_ID = "hairpin_stripline_bp" as const;
export const HAIRPIN_TOPOLOGY_IDS = [
  HAIRPIN_TOPOLOGY_ID,
  HAIRPIN_MITERED_TOPOLOGY_ID,
  HAIRPIN_STRIPLINE_TOPOLOGY_ID,
] as const;
export type HairpinTopologyId = (typeof HAIRPIN_TOPOLOGY_IDS)[number];

export const HAIRPIN_STEP_KEYS = ["topology", "parameters", "preview"] as const;
export type HairpinStepKey = (typeof HAIRPIN_STEP_KEYS)[number];
export type HairpinStep = 1 | 2 | 3;

/** Sent on every synthesis request. Not a form field; the synthesizer may floor it to 0.02 * h. */
export const HAIRPIN_INTRA_GAP_MM = 2;
/** Fixed layout. Not form fields. */
export const HAIRPIN_FEED_LEN_MM = 6;
export const HAIRPIN_BOARD_MARGIN_MM = 8;

export const HAIRPIN_RESPONSES = ["chebyshev", "butterworth", "equiripple"] as const;
export type HairpinResponse = (typeof HAIRPIN_RESPONSES)[number];

/** Wizard seeds. Dataclass ripple stays 0.5; this form sends 0.1. */
export interface HairpinParameterForm {
  f0: string;
  order: string;
  bw: string;
  response: HairpinResponse;
  ripple_db: string;
  z0: string;
  eps_r: string;
  h: string;
  tan_d: string;
}

export const HAIRPIN_FORM_DEFAULTS: HairpinParameterForm = {
  f0: "2",
  order: "3",
  bw: "0.2",
  response: "chebyshev",
  ripple_db: "0.1",
  z0: "50",
  eps_r: "4.2",
  h: "1.58",
  tan_d: "0.02",
};

const HAIRPIN_MICROSTRIP_STACK_DEFAULTS: Pick<HairpinParameterForm, "eps_r" | "h" | "tan_d"> = {
  eps_r: HAIRPIN_FORM_DEFAULTS.eps_r,
  h: HAIRPIN_FORM_DEFAULTS.h,
  tan_d: HAIRPIN_FORM_DEFAULTS.tan_d,
};

/** Matches ``HairpinStriplineBpSpec`` seed (εr, b, tan δ). */
const HAIRPIN_STRIPLINE_STACK_DEFAULTS: Pick<HairpinParameterForm, "eps_r" | "h" | "tan_d"> = {
  eps_r: "2.2",
  h: "3.2",
  tan_d: "0",
};

const NUMBER = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

export function parseHairpinNumber(raw: string): number | null {
  const text = raw.trim();
  if (!NUMBER.test(text)) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

function inClosedRange(value: number, min: number, max: number): boolean {
  return value >= min && value <= max;
}

export interface HairpinFieldIssue {
  field: keyof HairpinParameterForm;
  message: string;
}

/** Bounds that block İleri. Messages use a decimal point. */
export function hairpinParameterIssues(form: HairpinParameterForm): HairpinFieldIssue[] {
  const issues: HairpinFieldIssue[] = [];
  const push = (field: keyof HairpinParameterForm, message: string) => issues.push({ field, message });
  const order = parseHairpinNumber(form.order);
  if (order == null || !Number.isInteger(order) || order < 1) {
    push("order", t("hairpinDesigner.error.integer", { label: t("hairpinDesigner.field.order") }));
  }
  const f0 = parseHairpinNumber(form.f0);
  if (f0 == null || !inClosedRange(f0, 0.5, 30)) {
    push("f0", t("hairpinDesigner.error.range", { label: t("hairpinDesigner.field.f0"), min: "0.5", max: "30" }));
  }
  const bw = parseHairpinNumber(form.bw);
  if (bw == null || !inClosedRange(bw, 0.01, 10)) {
    push("bw", t("hairpinDesigner.error.range", { label: t("hairpinDesigner.field.bw"), min: "0.01", max: "10" }));
  } else if (f0 != null && f0 > 0 && !(bw / f0 > 0)) {
    push("bw", t("hairpinDesigner.error.fbw"));
  }
  if (form.response !== "butterworth") {
    if (!form.ripple_db.trim()) push("ripple_db", t("hairpinDesigner.error.ripple"));
    else if (parseHairpinNumber(form.ripple_db) == null) {
      push("ripple_db", t("hairpinDesigner.error.finite", { label: t("hairpinDesigner.field.ripple") }));
    }
  }
  const z0 = parseHairpinNumber(form.z0);
  if (z0 == null || !(z0 > 0)) push("z0", t("hairpinDesigner.error.positive", { label: t("hairpinDesigner.field.z0") }));
  const eps = parseHairpinNumber(form.eps_r);
  if (eps == null || !inClosedRange(eps, 1, 12)) {
    push("eps_r", t("hairpinDesigner.error.range", { label: t("hairpinDesigner.field.eps_r"), min: "1", max: "12" }));
  }
  const h = parseHairpinNumber(form.h);
  if (h == null || !(h > 0) || !inClosedRange(h, 0.1, 5)) {
    push("h", t("hairpinDesigner.error.range", { label: t("hairpinDesigner.field.h"), min: "0.1", max: "5" }));
  }
  const tanD = parseHairpinNumber(form.tan_d);
  if (tanD == null || !inClosedRange(tanD, 0, 0.1)) {
    push("tan_d", t("hairpinDesigner.error.range", { label: t("hairpinDesigner.field.tan_d"), min: "0", max: "0.1" }));
  }
  return issues;
}

export function hairpinSynthesisRequest(form: HairpinParameterForm = hairpinForm()): FilterSynthesisRequest {
  const f0 = Number(form.f0.trim());
  const bw = Number(form.bw.trim());
  const topology = isHairpinTopologySelected(hairpinTopology()) ? hairpinTopology()! : HAIRPIN_TOPOLOGY_ID;
  const stackKind = topology === HAIRPIN_STRIPLINE_TOPOLOGY_ID ? "stripline" : "microstrip";
  return {
    topology,
    electrical: {
      f0_hz: f0 * 1e9,
      bw_hz: bw * 1e9,
      order: Number(form.order.trim()),
      response: form.response,
      ripple_db: Number(form.ripple_db.trim()),
      z0: Number(form.z0.trim()),
    },
    stack: {
      stack_kind: stackKind,
      eps_r: Number(form.eps_r.trim()),
      thickness_mm: Number(form.h.trim()),
      tan_d: Number(form.tan_d.trim()),
    },
    layout: {
      feed_len_mm: HAIRPIN_FEED_LEN_MM,
      board_margin_mm: HAIRPIN_BOARD_MARGIN_MM,
      intra_gap_mm: HAIRPIN_INTRA_GAP_MM,
    },
    preview_only: false,
  };
}

const HAIRPIN_PREVIEW_DEBOUNCE_MS = 300;

export const [hairpinDesignerOpen, setHairpinDesignerOpen] = createSignal(false);
const [hairpinStep, setHairpinStepState] = createSignal<HairpinStep>(1);
export { hairpinStep };
/** Ideal J-inverter preview for step 2. Independent of the committed design. */
export const [hairpinLivePreview, setHairpinLivePreview] = createSignal<FilterSynthesisPreview | null>(null);
export const [hairpinTopology, setHairpinTopology] = createSignal<HairpinTopologyId | null>(null);
/** Set once step 2 has been edited. Escape then asks before discard. */
export const [hairpinDirty, setHairpinDirty] = createSignal(false);
export const [hairpinForm, setHairpinForm] = createSignal<HairpinParameterForm>({ ...HAIRPIN_FORM_DEFAULTS });
export const [hairpinSynthesis, setHairpinSynthesis] = createSignal<FilterSynthesisResponse | null>(null);
export const [hairpinSynthError, setHairpinSynthError] = createSignal("");
export const [hairpinSynthesizing, setHairpinSynthesizing] = createSignal(false);
export type HairpinSolveChoice = "closed_form" | "edc";
export const [hairpinSolveChoice, setHairpinSolveChoice] = createSignal<HairpinSolveChoice | null>(null);
export const [hairpinSolving, setHairpinSolving] = createSignal(false);
export const [hairpinSolveError, setHairpinSolveError] = createSignal("");
export const [hairpinEdc, setHairpinEdc] = createSignal<HairpinEdcStudy | null>(null);
/** Shared by preview dimension labels and the parameter table. */
export const [hairpinHighlightKey, setHairpinHighlightKey] = createSignal<string | null>(null);

let synthAbort: AbortController | null = null;
let previewTimer: ReturnType<typeof setTimeout> | null = null;
let previewAbort: AbortController | null = null;
let edcAbort: AbortController | null = null;
let edcStudyId: string | null = null;
let edcStop = false;
/** Closed-form seed from the last full synthesis. EDC may replace the design on the response. */
let closedFormDesign: Design | null = null;

export function hairpinStepKey(step: HairpinStep = hairpinStep()): HairpinStepKey {
  return HAIRPIN_STEP_KEYS[step - 1];
}

function cancelHairpinLivePreview() {
  if (previewTimer != null) {
    clearTimeout(previewTimer);
    previewTimer = null;
  }
  previewAbort?.abort();
  previewAbort = null;
}

/** Refresh the ideal S preview while step 2's form is valid. Keeps the last good curves otherwise. */
export function scheduleHairpinLivePreview() {
  if (previewTimer != null) clearTimeout(previewTimer);
  previewTimer = null;
  if (hairpinStep() !== 2 || hairpinParameterIssues(hairpinForm()).length > 0) return;
  previewTimer = setTimeout(() => {
    previewTimer = null;
    void runHairpinLivePreview();
  }, HAIRPIN_PREVIEW_DEBOUNCE_MS);
}

async function runHairpinLivePreview() {
  if (hairpinStep() !== 2 || hairpinParameterIssues(hairpinForm()).length > 0) return;
  previewAbort?.abort();
  const ctrl = new AbortController();
  previewAbort = ctrl;
  try {
    const result = await api.synthesizeFilter({ ...hairpinSynthesisRequest(), preview_only: true }, ctrl.signal);
    if (previewAbort !== ctrl || hairpinStep() !== 2) return;
    if (result.preview) {
      setHairpinLivePreview(result.preview);
      setHairpinSynthError("");
    }
  } catch (error) {
    if (ctrl.signal.aborted || hairpinStep() !== 2) return;
    setHairpinSynthError(errorText(error));
  } finally {
    if (previewAbort === ctrl) previewAbort = null;
  }
}

export function setHairpinStep(next: HairpinStep | ((prev: HairpinStep) => HairpinStep)) {
  const value = typeof next === "function" ? next(hairpinStep()) : next;
  setHairpinStepState(value);
  if (value === 2) scheduleHairpinLivePreview();
  else cancelHairpinLivePreview();
}

export function resetHairpinDesignerSession() {
  synthAbort?.abort();
  synthAbort = null;
  hairpinAbandonSolve();
  setHairpinStep(1);
  setHairpinLivePreview(null);
  setHairpinTopology(null);
  setHairpinDirty(false);
  setHairpinForm({ ...HAIRPIN_FORM_DEFAULTS });
  closedFormDesign = null;
  setHairpinSynthesis(null);
  setHairpinSynthError("");
  setHairpinSynthesizing(false);
  setHairpinSolveChoice(null);
  setHairpinSolving(false);
  setHairpinSolveError("");
  setHairpinEdc(null);
  setHairpinHighlightKey(null);
}

export function openHairpinDesigner() {
  resetHairpinDesignerSession();
  setHairpinDesignerOpen(true);
}

export function selectHairpinTopology(id: HairpinTopologyId) {
  setHairpinTopology(id);
  const stack =
    id === HAIRPIN_STRIPLINE_TOPOLOGY_ID ? HAIRPIN_STRIPLINE_STACK_DEFAULTS : HAIRPIN_MICROSTRIP_STACK_DEFAULTS;
  setHairpinForm({ ...hairpinForm(), ...stack });
}

export function patchHairpinForm(patch: Partial<HairpinParameterForm>) {
  setHairpinForm({ ...hairpinForm(), ...patch });
  setHairpinDirty(true);
  setHairpinSynthError("");
  scheduleHairpinLivePreview();
}

function isHairpinTopologySelected(id: string | null | undefined): id is HairpinTopologyId {
  return (HAIRPIN_TOPOLOGY_IDS as readonly string[]).includes(id ?? "");
}

/** Step 1 needs a hairpin card. Step 2 needs a valid form. Step 3 uses Finish. */
export function hairpinCanGoNext(): boolean {
  const step = hairpinStep();
  if (step === 1) return isHairpinTopologySelected(hairpinTopology());
  if (step === 2) return !hairpinSynthesizing() && hairpinParameterIssues(hairpinForm()).length === 0;
  return false;
}

export async function hairpinGoNext() {
  const step = hairpinStep();
  if (step === 1) {
    if (!isHairpinTopologySelected(hairpinTopology())) return;
    setHairpinStep(2);
    return;
  }
  if (step !== 2 || !hairpinCanGoNext()) return;
  cancelHairpinLivePreview();
  synthAbort?.abort();
  const ctrl = new AbortController();
  synthAbort = ctrl;
  setHairpinSynthesizing(true);
  setHairpinSynthError("");
  try {
    const result = await api.synthesizeFilter(hairpinSynthesisRequest(), ctrl.signal);
    if (synthAbort !== ctrl || hairpinStep() !== 2) return;
    setHairpinSynthesis(result);
    if (result.preview) setHairpinLivePreview(result.preview);
    closedFormDesign = result.design ?? null;
    setHairpinHighlightKey(null);
    setHairpinSolveChoice(null);
    setHairpinEdc(null);
    setHairpinSolveError("");
    setHairpinStep(3);
  } catch (error) {
    if (ctrl.signal.aborted || hairpinStep() !== 2) return;
    setHairpinSynthError(errorText(error));
  } finally {
    if (synthAbort === ctrl) {
      synthAbort = null;
      setHairpinSynthesizing(false);
    }
  }
}

/** Back keeps the selected card and typed values. Leaving preview while EDC runs asks, then cancels. */
export async function hairpinGoBack() {
  const step = hairpinStep();
  if (step <= 1) return;
  synthAbort?.abort();
  synthAbort = null;
  setHairpinSynthesizing(false);
  setHairpinSynthError("");
  if (step === 3 && hairpinEdc()?.status === "running") {
    if (!(await confirmDraftDiscard(t("hairpinDesigner.edc.backRunning")))) return;
    hairpinAbandonSolve();
  }
  if (hairpinStep() !== step) return;
  setHairpinStep((step - 1) as HairpinStep);
}

/** Closed Form is selected, or EDC finished and wrote a design. Commit stays on Finish. */
export function hairpinCanFinish(): boolean {
  const design = hairpinSynthesis()?.design;
  if (!design) return false;
  const choice = hairpinSolveChoice();
  if (choice === "closed_form") return true;
  return choice === "edc" && hairpinEdc()?.status === "done";
}

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    };
    if (signal.aborted) onAbort();
    else signal.addEventListener("abort", onAbort, { once: true });
  });
}

/** Stop a running study without replacing the step 3 seed. */
export function hairpinAbandonSolve() {
  edcStop = true;
  const id = edcStudyId;
  const running = hairpinEdc()?.status === "running";
  edcAbort?.abort();
  edcAbort = null;
  edcStudyId = null;
  if (id && running) {
    void api.hairpinEdc({ action: "cancel", study_id: id }).catch(() => undefined);
  }
  setHairpinEdc(null);
  setHairpinSolving(false);
}

/** "<name>", or "<name> 2", "<name> 3" when that file id is already a design or a model. */
function unusedDesignName(name: string, keys: readonly string[]): string {
  let n = name;
  for (let k = 2; k < 100 && keys.includes(freeDesignId(n, keys).id); k++) n = `${name} ${k}`;
  return n;
}

async function commitHairpinDesign(design: Design) {
  const base = design.model?.name?.trim() || "Hairpin";
  await refreshModels();
  const keys = models().map((m) => m.key);
  const name = unusedDesignName(base, keys);
  const id = freeDesignId(name, keys).id;
  const created = await createDesign({ id, name, design });
  if (!created) return;
  await openDesign(created.id);
  showToast(t("hairpinDesigner.solve.ready"), { key: "hairpin-ready" });
  setHairpinDesignerOpen(false);
}

export async function hairpinCancelEdc() {
  edcStop = true;
  const id = edcStudyId;
  edcAbort?.abort();
  if (!id) {
    setHairpinEdc(null);
    setHairpinSolving(false);
    return;
  }
  try {
    await api.hairpinEdc({ action: "cancel", study_id: id });
  } catch {
    /* Stay on preview. The closed-form seed is unchanged unless a study already finished. */
  } finally {
    edcStudyId = null;
    edcAbort = null;
    setHairpinEdc(null);
    setHairpinSolving(false);
  }
}

function restoreClosedFormDesign() {
  if (!closedFormDesign) return;
  const current = hairpinSynthesis();
  if (!current) return;
  setHairpinSynthesis({ ...current, design: closedFormDesign });
}

/** Choose Closed Form and drop a running EDC study. The dialog stays open. */
export function hairpinSelectClosedForm() {
  hairpinAbandonSolve();
  setHairpinEdc(null);
  restoreClosedFormDesign();
  setHairpinSolveChoice("closed_form");
  setHairpinSolveError("");
}

/** Choose EDC only. The study starts from hairpinStartEdc (explicit button). */
export function hairpinSelectEdc() {
  if (hairpinSolving()) return;
  if (hairpinSolveChoice() === "edc") return;
  hairpinAbandonSolve();
  setHairpinEdc(null);
  restoreClosedFormDesign();
  setHairpinSolveChoice("edc");
  setHairpinSolveError("");
}

/** Start the EDC study after the user chose EDC. On done, store the design and leave the dialog open. */
export async function hairpinStartEdc() {
  if (hairpinSolving()) return;
  if (hairpinSolveChoice() !== "edc") return;
  const edc = hairpinEdc();
  if (edc?.status === "running" || edc?.status === "done") return;
  setHairpinSolveError("");
  const design = closedFormDesign ?? hairpinSynthesis()?.design;
  const electrical = hairpinSynthesisRequest().electrical;
  if (!design || !electrical) return;
  edcStop = false;
  const ctrl = new AbortController();
  edcAbort = ctrl;
  setHairpinSolving(true);
  try {
    let study = await api.hairpinEdc({ action: "start", design, electrical }, ctrl.signal);
    edcStudyId = study.id;
    setHairpinEdc(study);
    while (study.status === "running" && !edcStop && !ctrl.signal.aborted) {
      await wait(800, ctrl.signal);
      if (edcStop || ctrl.signal.aborted) break;
      study = await api.hairpinEdc({ action: "poll", study_id: study.id }, ctrl.signal);
      if (edcStop || ctrl.signal.aborted || hairpinSolveChoice() !== "edc") break;
      setHairpinEdc(study);
    }
    if (!edcStop && hairpinSolveChoice() === "edc" && study.status === "done" && study.design) {
      const current = hairpinSynthesis();
      if (current) setHairpinSynthesis({ ...current, design: study.design });
      setHairpinEdc(study);
      return;
    }
    if (!edcStop && study.status === "failed") {
      setHairpinEdc(null);
      setHairpinSolveError(study.error || t("hairpinDesigner.solve.failed"));
    }
  } catch (error) {
    if (edcStop || (error instanceof DOMException && error.name === "AbortError")) return;
    setHairpinEdc(null);
    setHairpinSolveError(errorText(error));
  } finally {
    if (edcAbort === ctrl) {
      edcAbort = null;
      setHairpinSolving(false);
    }
  }
}

/** Commit the current design. Closed Form uses the seed; EDC uses the study result. */
export async function hairpinFinish() {
  if (!hairpinCanFinish()) return;
  const design = hairpinSynthesis()?.design;
  if (!design) return;
  setHairpinSolving(true);
  setHairpinSolveError("");
  try {
    await commitHairpinDesign(design);
  } catch (error) {
    setHairpinSolveError(errorText(error));
  } finally {
    setHairpinSolving(false);
  }
}
