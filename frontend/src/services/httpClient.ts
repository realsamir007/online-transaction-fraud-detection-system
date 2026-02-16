const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function createRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

type RequestOptions = {
  method?: HttpMethod;
  body?: unknown;
  authToken?: string;
  adminApiKey?: string;
};

async function parseError(response: Response): Promise<ApiError> {
  let message = `Request failed with status ${response.status}`;

  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    if (payload.detail) {
      message = payload.detail;
    } else if (payload.message) {
      message = payload.message;
    }
  } catch {
    // keep default message
  }

  return new ApiError(response.status, message);
}

export async function requestJson<T>(path: string, options?: RequestOptions): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Request-ID": createRequestId(),
  };

  if (options?.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  if (options?.authToken) {
    headers.Authorization = `Bearer ${options.authToken}`;
  }

  if (options?.adminApiKey) {
    headers["X-Admin-Key"] = options.adminApiKey;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options?.method ?? "GET",
    headers,
    body: options?.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  return (await response.json()) as T;
}

export { API_BASE_URL };
