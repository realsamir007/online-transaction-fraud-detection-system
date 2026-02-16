import type {
  AdminAccountsResponse,
  AdminTransferRow,
  AdminTransfersResponse,
  AdminUnblockUserRequest,
  AdminUnblockUserResponse,
  AdminUpdateBalanceRequest,
  AdminUpdateBalanceResponse,
  AdminUsersResponse,
} from "../types";
import { ApiError, requestJson } from "./httpClient";

export async function validateAdminApiKey(adminApiKey: string): Promise<boolean> {
  if (!adminApiKey.trim()) {
    return false;
  }

  try {
    await requestJson<AdminUnblockUserResponse>("/banking/admin/unblock-user", {
      method: "POST",
      adminApiKey,
      body: {},
    });
    return true;
  } catch (error) {
    if (error instanceof ApiError && error.status === 400) {
      return true;
    }
    return false;
  }
}

export function adminUnblockUser(
  adminApiKey: string,
  payload: AdminUnblockUserRequest,
): Promise<AdminUnblockUserResponse> {
  return requestJson<AdminUnblockUserResponse>("/banking/admin/unblock-user", {
    method: "POST",
    adminApiKey,
    body: payload,
  });
}

export async function fetchAdminUsers(
  adminApiKey: string,
  limit = 50,
  offset = 0,
): Promise<AdminUsersResponse> {
  return requestJson<AdminUsersResponse>(`/banking/admin/users?limit=${limit}&offset=${offset}`, {
    adminApiKey,
  });
}

export async function fetchAdminAccounts(
  adminApiKey: string,
  limit = 50,
  offset = 0,
): Promise<AdminAccountsResponse> {
  return requestJson<AdminAccountsResponse>(`/banking/admin/accounts?limit=${limit}&offset=${offset}`, {
    adminApiKey,
  });
}

export async function updateAdminAccountBalance(
  adminApiKey: string,
  accountId: string,
  payload: AdminUpdateBalanceRequest,
): Promise<AdminUpdateBalanceResponse> {
  return requestJson<AdminUpdateBalanceResponse>(`/banking/admin/accounts/${accountId}/balance`, {
    method: "PATCH",
    adminApiKey,
    body: payload,
  });
}

export async function fetchAdminTransfers(
  adminApiKey: string,
  limit = 50,
  offset = 0,
): Promise<AdminTransfersResponse> {
  return requestJson<AdminTransfersResponse>(`/banking/admin/transfers?limit=${limit}&offset=${offset}`, {
    adminApiKey,
  });
}

export function mapTransferRisk(riskScore: number | null | undefined): string {
  if (riskScore === null || riskScore === undefined) {
    return "N/A";
  }
  if (riskScore <= 0.1) {
    return "LOW";
  }
  if (riskScore <= 0.5) {
    return "MEDIUM";
  }
  return "HIGH";
}

export function enrichTransferRows(rows: AdminTransferRow[]): AdminTransferRow[] {
  return rows.map((row) => ({
    ...row,
    risk_score: row.risk_score,
  }));
}
