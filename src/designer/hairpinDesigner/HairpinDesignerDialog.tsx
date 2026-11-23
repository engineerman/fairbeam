import { For, Show, onCleanup } from "solid-js";
import { X } from "lucide-solid";
import { useModal } from "../../lib/dialog";
import { confirmDraftDiscard } from "../../lib/ConfirmDialog";
import { t } from "../../i18n";
import ParametersStep from "./ParametersStep.tsx";
import PreviewStep from "./PreviewStep.tsx";
import TopologyStep from "./TopologyStep.tsx";
import {
  HAIRPIN_STEP_KEYS,
  hairpinAbandonSolve,
  hairpinCanFinish,
  hairpinCanGoNext,
  hairpinDirty,
  hairpinDesignerOpen,
  hairpinFinish,
  hairpinGoBack,
  hairpinGoNext,
  hairpinSolving,
  hairpinStep,
  hairpinStepKey,
  hairpinSynthesizing,
  resetHairpinDesignerSession,
  setHairpinDesignerOpen,
} from "./state";
import "../../styles/hairpin-designer.css";

export default function HairpinDesignerDialog() {
  let box: HTMLDivElement | undefined;
  const close = async () => {
    if (hairpinDirty() && !(await confirmDraftDiscard(t("hairpinDesigner.discard")))) return;
    hairpinAbandonSolve();
    setHairpinDesignerOpen(false);
  };
  useModal(() => box, close);
  onCleanup(() => resetHairpinDesignerSession());

  return (
    <Show when={hairpinDesignerOpen()}>
      <div class="scrim">
        <div class="dialog hd-dialog" classList={{ "hd-dialog-preview": hairpinStep() === 3 }} role="dialog" aria-modal="true" aria-labelledby="hd-title" ref={box} tabindex={-1}>
          <div class="dialog-head">
            <div>
              <h2 id="hd-title">{t(`hairpinDesigner.step.${hairpinStepKey()}`)}</h2>
              <ol class="hd-steps">
                <For each={HAIRPIN_STEP_KEYS}>
                  {(key) => <li aria-current={hairpinStepKey() === key ? "step" : undefined}>{t(`hairpinDesigner.step.${key}`)}</li>}
                </For>
              </ol>
            </div>
            <button type="button" class="icon-btn" aria-label={t("common.close")} onClick={() => void close()}><X size={18} /></button>
          </div>
          <div class="dialog-body hd-body">
            <Show when={hairpinStep() === 1}>
              <TopologyStep />
            </Show>
            <Show when={hairpinStep() === 2}>
              <ParametersStep />
            </Show>
            <Show when={hairpinStep() === 3}>
              <PreviewStep />
            </Show>
          </div>
          <div class="dialog-foot">
            <Show when={hairpinStep() > 1}>
              <button type="button" class="btn btn-ghost" onClick={() => void hairpinGoBack()}>{t("hairpinDesigner.back")}</button>
            </Show>
            <div class="dialog-actions">
              <button type="button" class="btn btn-ghost" onClick={() => void close()}>{t("common.cancel")}</button>
              <Show when={hairpinStep() < 3} fallback={
                <button type="button" class="btn btn-primary" disabled={!hairpinCanFinish()} aria-busy={hairpinSolving()}
                  onClick={() => void hairpinFinish()}>{t("hairpinDesigner.finish")}</button>
              }>
                <Show when={hairpinStep() > 1}>
                  <button type="button" class="btn btn-primary" disabled={!hairpinCanGoNext()} aria-busy={hairpinSynthesizing()}
                    onClick={() => void hairpinGoNext()}>{t("hairpinDesigner.next")}</button>
                </Show>
              </Show>
            </div>
          </div>
        </div>
      </div>
    </Show>
  );
}
