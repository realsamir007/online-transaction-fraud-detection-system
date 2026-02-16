import type {
  AdminUnblockUserRequest,
  AdminUnblockUserResponse,
  DemoSeedResponse,
  DashboardResponse,
  InitiateTransferRequest,
  ReceiverValidationRequest,
  ReceiverValidationResponse,
  TransactionHistoryResponse,
  TransferInitiateResponse,
  TransferMfaChallengeResponse,
  TransferMfaVerifyRequest,
} from "../types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

function createRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function parseJsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const errorPayload = (await response.json()) as { detail?: string };
      if (errorPayload.detail) {
        detail = errorPayload.detail;
      }
    } catch {
      // keep fallback detail
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

async function authFetch<T>(
  path: string,
  accessToken: string,
  options?: { method?: "GET" | "POST"; body?: unknown },
): Promise<T> {
  const requestId = createRequestId();
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      "X-Request-ID": requestId,
    },
    body: options?.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  return parseJsonOrThrow<T>(response);
}

async function adminFetch<T>(
  path: string,
  adminApiKey: string,
  options?: { method?: "GET" | "POST"; body?: unknown },
): Promise<T> {
  const requestId = createRequestId();
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": adminApiKey,
      "X-Request-ID": requestId,
    },
    body: options?.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  return parseJsonOrThrow<T>(response);
}

export async function fetchDashboard(accessToken: string): Promise<DashboardResponse> {
  return authFetch<DashboardResponse>("/banking/dashboard", accessToken);
}

export async function seedDemoBankingData(accessToken: string): Promise<DemoSeedResponse> {
  return authFetch<DemoSeedResponse>("/banking/demo/seed", accessToken, {
    method: "POST",
  });
}

export async function fetchTransactionHistory(
  accessToken: string,
  limit = 50,
  offset = 0,
): Promise<TransactionHistoryResponse> {
  return authFetch<TransactionHistoryResponse>(
    `/banking/transactions?limit=${limit}&offset=${offset}`,
    accessToken,
  );
}

export async function validateReceiver(
  accessToken: string,
  payload: ReceiverValidationRequest,
): Promise<ReceiverValidationResponse> {
  return authFetch<ReceiverValidationResponse>("/banking/validate-receiver", accessToken, {
    method: "POST",
    body: payload,
  });
}

export async function initiateTransfer(
  accessToken: string,
  payload: InitiateTransferRequest,
): Promise<TransferInitiateResponse> {
  return authFetch<TransferInitiateResponse>("/banking/transfers/initiate", accessToken, {
    method: "POST",
    body: payload,
  });
}

export async function requestTransferMfaChallenge(
  accessToken: string,
  transferId: string,
): Promise<TransferMfaChallengeResponse> {
  return authFetch<TransferMfaChallengeResponse>(`/banking/transfers/${transferId}/mfa/challenge`, accessToken, {
    method: "POST",
  });
}

export async function verifyTransferMfa(
  accessToken: string,
  transferId: string,
  payload: TransferMfaVerifyRequest,
): Promise<TransferInitiateResponse> {
  return authFetch<TransferInitiateResponse>(`/banking/transfers/${transferId}/mfa/verify`, accessToken, {
    method: "POST",
    body: payload,
  });
}

export async function adminUnblockUser(
  adminApiKey: string,
  payload: AdminUnblockUserRequest,
): Promise<AdminUnblockUserResponse> {
  return adminFetch<AdminUnblockUserResponse>("/banking/admin/unblock-user", adminApiKey, {
    method: "POST",
    body: payload,
  });
}
