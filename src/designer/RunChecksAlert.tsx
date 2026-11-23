import { For, Show } from "solid-js";
import { CircleAlert } from "lucide-solid";
import { t } from "../i18n";
import { addPort, applyFix, checks, draft, focusPath } from "./store";
import { checkFixLabel, checkTitle } from "./checkText";
import { checkAction } from "./checkActions";
import { checkPlace, kindLabel } from "./DesignPane";
import { humanizePaths } from "./pathText";

/** openEMS Run dialog error block; reuse on EMerge/Elmer Run forms for Checks parity. */
export default function RunChecksAlert(props: { onNavigate?: () => void }) {
  const errors = () => checks().filter((c) => c.severity === "error");
  const go = (path: string) => {
    props.onNavigate?.();
    focusPath(path);
  };
  return (
    <Show when={errors().length}>
      <div class="status-block status-critical" role="alert" data-testid="run-checks-errors">
        <CircleAlert size={14} aria-hidden="true" />
        <div>
          <p>{t("run.fixErrors", { count: errors().length })}</p>
          <ul class="rd-errors">
            <For each={errors().slice(0, 6)}>{(c) => (
              <li>
                <button type="button" class="linklike" onClick={() => go(c.path)}>{humanizePaths(checkTitle(c), draft, kindLabel)}</button>
                <span class="rd-where">
                  <span class="muted">{checkPlace(c)}</span>
                  <Show when={c.fix}>{(f) => <button type="button" class="btn btn-ghost btn-sm rd-fix" onClick={() => applyFix(f().set)}>{checkFixLabel(c)}</button>}</Show>
                  <Show when={checkAction(c, draft.ports?.length ?? 0)}><button type="button" class="btn btn-ghost btn-sm rd-fix" onClick={() => { props.onNavigate?.(); addPort(); }}>{t("contextMenu.addPort")}</button></Show>
                </span>
              </li>
            )}</For>
          </ul>
          <Show when={errors().length > 6}><p class="muted">{t("run.moreErrors", { count: errors().length - 6 })}</p></Show>
        </div>
      </div>
    </Show>
  );
}
