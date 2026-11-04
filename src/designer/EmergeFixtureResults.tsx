import { For } from "solid-js";
import type { ResearchResult } from "../runner/api";
import { fmt, t } from "../i18n";

const db = (abs: number) => 20 * Math.log10(Math.max(1e-15, abs));

/** WR-90 waveguide fixture table for schema fairbeam.emerge-fixture-result/1. */
export default function EmergeFixtureResults(props: { result: ResearchResult }) {
  const r = () => props.result;
  const metrics = () => r().metrics ?? {};
  const criteria = () => r().criteria ?? {};
  const abs11 = () => metrics().s11_abs ?? r().frequency_hz.map((_, i) => Math.hypot(r().s11_re?.[i] ?? NaN, r().s11_im?.[i] ?? NaN));
  const abs21 = () => metrics().s21_abs ?? r().frequency_hz.map((_, i) => Math.hypot(r().s21_re?.[i] ?? NaN, r().s21_im?.[i] ?? NaN));
  const phase = () => metrics().phase_error_deg ?? [];
  return <section class="stack" data-emerge-results aria-label={t("research.emerge.resultNote")}>
    <p class="note">{t("research.emerge.resultNote")}</p>
    <p class="status-block" classList={{ "status-good": r().status === "results_validated", "status-warn": r().status !== "results_validated" }} role="status">
      {t(r().status === "results_validated" ? "research.emerge.validated" : "research.qaUnvalidated")}
    </p>
    <table class="table">
      <caption>{t("research.emerge.frequencies")}</caption>
      <thead><tr>
        <th class="num">{t("research.frequency")}</th>
        <th class="num">|S11| <span class="th-unit">dB</span></th>
        <th class="num">|S21|</th>
        <th class="num">{t("research.emerge.phaseError")}</th>
      </tr></thead>
      <tbody>
        <For each={r().frequency_hz}>{(f, i) => <tr>
          <td class="num">{fmt.fixed(f / 1e9, 1)}</td>
          <td class="num">{fmt.fixed(db(abs11()[i()] ?? NaN), 3)}</td>
          <td class="num">{fmt.fixed(abs21()[i()] ?? NaN, 5)}</td>
          <td class="num">{fmt.fixed(phase()[i()] ?? NaN, 3)}</td>
        </tr>}</For>
      </tbody>
    </table>
    <dl class="kv">
      <dt>{t("research.emerge.criteria")}</dt>
      <dd>|S11| ≤ {fmt.fixed(criteria().s11_max ?? NaN, 3)}, |S21| ≥ {fmt.fixed(criteria().s21_min ?? NaN, 3)},
        {" "}{t("research.emerge.phaseError")} ≤ {fmt.fixed(criteria().phase_error_deg_max ?? NaN, 1)}°,
        {" "}passivity ≤ {fmt.fixed(criteria().passivity_max ?? NaN, 3)}</dd>
      <dt>{t("research.emerge.metrics")}</dt>
      <dd>|S11|max = {fmt.fixed(metrics().s11_max ?? NaN, 5)}, |S21|min = {fmt.fixed(metrics().s21_min ?? NaN, 5)},
        {" "}{t("research.emerge.phaseError")} = {fmt.fixed(metrics().phase_error_deg_max ?? NaN, 3)}°,
        {" "}passivity = {fmt.fixed(metrics().passivity_max ?? NaN, 5)}</dd>
    </dl>
  </section>;
}
