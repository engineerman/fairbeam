import { For, Show } from "solid-js";
import { t } from "../../i18n";
import PreviewPlot from "./PreviewPlot";
import StackUpDiagram from "./StackUpDiagram";
import {
  HAIRPIN_RESPONSES,
  hairpinForm,
  hairpinParameterIssues,
  hairpinSynthError,
  patchHairpinForm,
  type HairpinFieldIssue,
  type HairpinParameterForm,
  type HairpinResponse,
} from "./state";

type NumberFieldId = Exclude<keyof HairpinParameterForm, "response">;

function invalid(id: NumberFieldId, issues: HairpinFieldIssue[]): boolean {
  return issues.some((issue) => issue.field === id);
}

function fieldLabel(id: NumberFieldId): string {
  if (id === "f0") return t("hairpinDesigner.field.f0");
  if (id === "order") return t("hairpinDesigner.field.order");
  if (id === "bw") return t("hairpinDesigner.field.bw");
  if (id === "ripple_db") return t("hairpinDesigner.field.ripple");
  if (id === "z0") return t("hairpinDesigner.field.z0");
  if (id === "eps_r") return t("hairpinDesigner.field.eps_r");
  if (id === "h") return t("hairpinDesigner.field.h");
  return t("hairpinDesigner.field.tan_d");
}

function NumberField(props: { id: NumberFieldId; issues: HairpinFieldIssue[] }) {
  const spin = () => props.id === "order";
  return (
    <label class="field">
      <span>{fieldLabel(props.id)}</span>
      <input
        id={`hd-${props.id}`}
        type={spin() ? "number" : "text"}
        inputMode={spin() ? "numeric" : "decimal"}
        step={spin() ? 1 : undefined}
        min={spin() ? 1 : undefined}
        autocomplete="off"
        spellcheck={false}
        data-field={props.id}
        value={hairpinForm()[props.id]}
        aria-invalid={invalid(props.id, props.issues)}
        onInput={(event) => patchHairpinForm({ [props.id]: event.currentTarget.value })}
      />
    </label>
  );
}

export default function ParametersStep() {
  const issues = () => hairpinParameterIssues(hairpinForm());
  const form = hairpinForm;
  return (
    <div class="hd-params">
      <div class="hd-params-form">
        <section class="hd-group" aria-labelledby="hd-group-electrical">
          <h3 id="hd-group-electrical">{t("hairpinDesigner.group.electrical")}</h3>
          <div class="hd-fields">
            <NumberField id="f0" issues={issues()} />
            <NumberField id="order" issues={issues()} />
            <NumberField id="bw" issues={issues()} />
            <label class="field">
              <span>{t("hairpinDesigner.field.response")}</span>
              <select
                id="hd-response"
                class="rp-input"
                data-field="response"
                value={form().response}
                onChange={(event) => patchHairpinForm({ response: event.currentTarget.value as HairpinResponse })}
              >
                <For each={HAIRPIN_RESPONSES}>
                  {(id) => <option value={id}>{t(`hairpinDesigner.response.${id}`)}</option>}
                </For>
              </select>
            </label>
            <NumberField id="z0" issues={issues()} />
          </div>
          <Show when={form().response !== "butterworth"}>
            <details class="hd-advanced">
              <summary>{t("hairpinDesigner.advanced")}</summary>
              <NumberField id="ripple_db" issues={issues()} />
            </details>
          </Show>
        </section>
        <section class="hd-group" aria-labelledby="hd-group-stack">
          <h3 id="hd-group-stack">{t("hairpinDesigner.group.stack")}</h3>
          <div class="hd-fields">
            <NumberField id="eps_r" issues={issues()} />
            <NumberField id="h" issues={issues()} />
            <NumberField id="tan_d" issues={issues()} />
          </div>
        </section>
        <Show when={issues().length}>
          <div class="status-block status-critical" role="alert">
            <ul class="hd-issues">
              <For each={issues()}>{(issue) => <li>{issue.message}</li>}</For>
            </ul>
          </div>
        </Show>
        <Show when={hairpinSynthError()}>
          <p class="status-block status-critical" role="alert">{hairpinSynthError()}</p>
        </Show>
      </div>
      <div class="hd-params-side">
        <PreviewPlot />
        <StackUpDiagram eps_r={form().eps_r} h={form().h} tan_d={form().tan_d} />
      </div>
    </div>
  );
}
