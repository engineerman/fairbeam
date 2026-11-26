// Run-panel sweeps do not open SweepDialog. This registers the same EMerge request that dialog sends.
import { t } from "../i18n";
import { hasDocumentResultScope } from "../lib/nativeDocuments";
import { api } from "../runner/api";
import { setEmergeSweepAttach } from "../runner/emergeSweepAttach";
import { currentModel } from "../runner/store";
import { currentEmergeMapKind, emergeResearchSource, emergeSolveRequest } from "./emergeRunRequest";
import { file as designFile } from "./store";

setEmergeSweepAttach(async () => {
  const saved = designFile();
  const model = currentModel();
  if (!saved || !model || saved.id !== model.key) throw new Error(t("sweep.err.noDesign"));
  const probed = await api.health();
  const source = emergeResearchSource(probed, saved);
  if (hasDocumentResultScope(saved) && !source) throw new Error(t("emergeExp.serverUpdate"));
  return emergeSolveRequest(saved.design.ports, currentEmergeMapKind(saved.design.ports), source);
});
