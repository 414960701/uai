export type ResourceStatus = "idle" | "loading" | "ready" | "stale" | "error";

export type ResourceState<T> = {
  status: ResourceStatus;
  data: T;
  message?: string;
  code?: string;
};

export function resourceState<T>(data: T, status: ResourceStatus = "idle"): ResourceState<T> {
  return { status, data };
}

export function markResourceError<T>(
  previous: ResourceState<T>,
  problem: { message?: string; problem?: { code?: string } },
): ResourceState<T> {
  const hasData = Array.isArray(previous.data)
    ? previous.data.length > 0
    : previous.data !== null && previous.data !== undefined;
  return {
    status: hasData ? "stale" : "error",
    data: previous.data,
    message: problem.message || "资源暂时不可用",
    code: problem.problem?.code,
  };
}
