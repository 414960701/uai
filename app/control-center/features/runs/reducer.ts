export type RunEvent = {
  run_id: string;
  sequence: number;
  type: string;
  timestamp: string;
  agent_id: string;
  parent_agent_id?: string;
  depth: number;
  payload: Record<string, unknown>;
};

export type RunTerminalStatus = "running" | "succeeded" | "failed" | "cancelled";

/** Sequence is the durable identity of an event within one Run. */
export function mergeRunEvents(current: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const bySequence = new Map<number, RunEvent>();
  for (const event of [...current, ...incoming]) {
    if (!Number.isInteger(event.sequence) || event.sequence < 1) continue;
    if (!bySequence.has(event.sequence)) bySequence.set(event.sequence, event);
  }
  return Array.from(bySequence.values()).sort((left, right) => left.sequence - right.sequence);
}

export function terminalStatusForEvent(event: RunEvent): RunTerminalStatus | undefined {
  if (event.type === "run.completed") return "succeeded";
  if (event.type === "run.failed") return "failed";
  if (event.type === "run.cancelled") return "cancelled";
  if (event.type === "run.started") return "running";
  return undefined;
}
