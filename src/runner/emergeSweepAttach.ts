/** Designer-registered EMerge body for a Run-panel sweep. Absent means do not queue openEMS. */
export type EmergeSweepBody = {
  path: string;
  settings: Record<string, unknown>;
  source?: { model_id: string; workspace_hash: string; backup_scope: string };
};

let attach: (() => Promise<EmergeSweepBody>) | null = null;

export function setEmergeSweepAttach(fn: () => Promise<EmergeSweepBody>): void {
  attach = fn;
}

export function emergeSweepAttach(): Promise<EmergeSweepBody> | null {
  return attach ? attach() : null;
}
