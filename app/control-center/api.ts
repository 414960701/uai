export type ProblemDetails = {
  type?: string;
  code: string;
  message: string;
  field_errors?: Array<{ field: string; code: string; message: string }>;
  resource?: { type: string; id?: string | null } | null;
  retryable?: boolean;
  remediation?: { action: string; target?: string | null } | null;
  correlation_id?: string;
};

const PROBLEM_MESSAGES: Record<string, string> = {
  "auth.invalid": "控制面凭证无效或尚未配置",
  "request.invalid": "请检查标记为错误的字段",
  "request.rejected": "请求未通过控制面校验，请检查配置",
  "request.version_required": "请先重新加载当前资源，再提交修改",
  "resource.not_found": "资源不存在，可能已被删除或不属于当前数据分区",
  "resource.conflict": "当前操作与资源状态冲突，请检查状态后重试",
  "resource.version_conflict": "资源已被其他操作更新，请重新加载并比较",
  "model_config.unavailable": "模型连接当前不可运行，请先检查并启用它",
  "endpoint.scheme_not_allowed": "端点协议不被允许",
  "endpoint.userinfo_not_allowed": "端点不得包含用户名或密码",
  "endpoint.host_required": "端点必须包含主机名",
  "endpoint.query_or_fragment_not_allowed": "端点不得包含查询参数或片段",
  "endpoint.private_address_not_allowed": "端点目标地址未通过安全策略",
  "endpoint.https_required": "公网模型端点必须使用 HTTPS",
  "endpoint.port_invalid": "端口号无效",
  "server.request_failed": "控制面暂时无法完成请求，请稍后重试",
  "server.internal_error": "控制面暂时无法完成请求，请稍后重试",
};

export type ServerSentEvent<T> = {
  id?: string;
  event?: string;
  data: T;
};

export class ApiProblem extends Error {
  problem: ProblemDetails;
  status: number;

  constructor(problem: ProblemDetails, status: number) {
    super(problem.message);
    this.name = "ApiProblem";
    this.problem = problem;
    this.status = status;
  }
}

function isProblemDetails(value: unknown): value is ProblemDetails {
  return Boolean(
    value &&
      typeof value === "object" &&
      "code" in value &&
      typeof (value as { code?: unknown }).code === "string" &&
      typeof (value as { message?: unknown }).message === "string",
  );
}

export function problemFromUnknown(value: unknown, status = 0): ApiProblem {
  if (isProblemDetails(value)) return new ApiProblem(value, status);
  const legacy = value && typeof value === "object" && "detail" in value
    ? (value as { detail?: unknown }).detail
    : undefined;
  const code = legacy && typeof legacy === "object" && "code" in legacy
    ? String((legacy as { code?: unknown }).code || "request.failed")
    : status === 401
      ? "auth.invalid"
      : status === 404
        ? "resource.not_found"
        : "request.failed";
  return new ApiProblem(
    {
      code,
      message: status >= 500 ? "控制面暂时无法完成请求" : "请求未通过控制面校验",
      retryable: status >= 500,
      remediation: { action: status >= 500 ? "retry" : "review_request", target: "request" },
    },
    status,
  );
}

export async function apiRequest<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, options);
  } catch {
    throw problemFromUnknown(undefined, 0);
  }
  let body: unknown = undefined;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  if (!response.ok) throw problemFromUnknown(body, response.status);
  return body as T;
}

/**
 * Consume a fetch-based SSE stream so the control-plane credential and tenant
 * headers can be sent without putting either value in a URL.  The helper only
 * exposes parsed event data; comments and keepalives are intentionally
 * ignored.
 */
export async function consumeEventStream<T>(
  url: string,
  options: RequestInit,
  onEvent: (event: ServerSentEvent<T>) => void,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        Accept: "text/event-stream",
        ...(options.headers || {}),
      },
    });
  } catch {
    throw problemFromUnknown(undefined, 0);
  }
  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    throw problemFromUnknown(body, response.status);
  }
  if (!response.body) throw new Error("事件流没有可读取的响应体");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventId: string | undefined;
  let eventName: string | undefined;
  let dataLines: string[] = [];

  const dispatch = () => {
    if (!dataLines.length) {
      eventId = undefined;
      eventName = undefined;
      return;
    }
    const data = dataLines.join("\n");
    try {
      onEvent({
        id: eventId,
        event: eventName,
        data: JSON.parse(data) as T,
      });
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error("事件流数据格式无效");
      throw error;
    } finally {
      eventId = undefined;
      eventName = undefined;
      dataLines = [];
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line) {
        dispatch();
        continue;
      }
      if (line.startsWith(":")) continue;
      const separator = line.indexOf(":");
      const field = separator === -1 ? line : line.slice(0, separator);
      const rawValue = separator === -1 ? "" : line.slice(separator + 1).replace(/^ /, "");
      if (field === "id") eventId = rawValue;
      else if (field === "event") eventName = rawValue;
      else if (field === "data") dataLines.push(rawValue);
    }
    if (done) {
      if (buffer) {
        if (buffer.startsWith("data:")) dataLines.push(buffer.slice(5).replace(/^ /, ""));
        else if (buffer.startsWith("id:")) eventId = buffer.slice(3).replace(/^ /, "");
        else if (buffer.startsWith("event:")) eventName = buffer.slice(6).replace(/^ /, "");
      }
      dispatch();
      return;
    }
  }
}

export function headersFor(apiKey: string, tenantId = "default"): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Tenant-ID": tenantId,
  };
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
  return headers;
}

export function problemMessage(problem: unknown, fallback = "操作未完成") {
  if (problem instanceof ApiProblem) {
    return PROBLEM_MESSAGES[problem.problem.code] || fallback;
  }
  if (problem instanceof Error) return problem.message || fallback;
  return fallback;
}

export function problemFieldMessage(problem: unknown, field: string): string | undefined {
  if (!(problem instanceof ApiProblem)) return undefined;
  return problem.problem.field_errors?.find((item) => item.field === field)?.message;
}

export function problemCode(problem: unknown): string | undefined {
  return problem instanceof ApiProblem ? problem.problem.code : undefined;
}
