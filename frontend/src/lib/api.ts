import type { PredictionResult, TransactionPayload } from "../types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

function createRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function predictTransaction(
  payload: TransactionPayload,
  accessToken: string,
): Promise<PredictionResult> {
  const requestId = createRequestId();
  const response = await fetch(`${apiBaseUrl}/predict-transaction`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      "X-Request-ID": requestId,
    },
    body: JSON.stringify(payload),
  });

  const responseRequestId = response.headers.get("X-Request-ID") || requestId;

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const errorPayload = (await response.json()) as { detail?: string };
      if (errorPayload.detail) {
        detail = errorPayload.detail;
      }
    } catch {
      // Keep fallback detail.
    }
    throw new Error(detail);
  }

  const body = (await response.json()) as Omit<PredictionResult, "requestId">;
  return {
    ...body,
    requestId: responseRequestId,
  };
}

