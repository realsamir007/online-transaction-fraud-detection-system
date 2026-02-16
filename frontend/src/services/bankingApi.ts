import type {
  DashboardResponse,
  DemoSeedResponse,
  InitiateTransferRequest,
  ReceiverValidationRequest,
  ReceiverValidationResponse,
  TransactionHistoryResponse,
  TransferInitiateResponse,
  TransferMfaChallengeResponse,
  TransferMfaVerifyRequest,
} from "../types";
import { requestJson } from "./httpClient";

export function fetchDashboard(accessToken: string): Promise<DashboardResponse> {
  return requestJson<DashboardResponse>("/banking/dashboard", {
    authToken: accessToken,
  });
}

export function fetchTransactionHistory(
  accessToken: string,
  limit = 20,
  offset = 0,
): Promise<TransactionHistoryResponse> {
  return requestJson<TransactionHistoryResponse>(`/banking/transactions?limit=${limit}&offset=${offset}`, {
    authToken: accessToken,
  });
}

export function seedDemoBankingData(accessToken: string): Promise<DemoSeedResponse> {
  return requestJson<DemoSeedResponse>("/banking/demo/seed", {
    method: "POST",
    authToken: accessToken,
  });
}

export function validateReceiver(
  accessToken: string,
  payload: ReceiverValidationRequest,
): Promise<ReceiverValidationResponse> {
  return requestJson<ReceiverValidationResponse>("/banking/validate-receiver", {
    method: "POST",
    authToken: accessToken,
    body: payload,
  });
}

export function initiateTransfer(
  accessToken: string,
  payload: InitiateTransferRequest,
): Promise<TransferInitiateResponse> {
  return requestJson<TransferInitiateResponse>("/banking/transfers/initiate", {
    method: "POST",
    authToken: accessToken,
    body: payload,
  });
}

export function requestTransferMfaChallenge(
  accessToken: string,
  transferId: string,
): Promise<TransferMfaChallengeResponse> {
  return requestJson<TransferMfaChallengeResponse>(`/banking/transfers/${transferId}/mfa/challenge`, {
    method: "POST",
    authToken: accessToken,
  });
}

export function verifyTransferMfa(
  accessToken: string,
  transferId: string,
  payload: TransferMfaVerifyRequest,
): Promise<TransferInitiateResponse> {
  return requestJson<TransferInitiateResponse>(`/banking/transfers/${transferId}/mfa/verify`, {
    method: "POST",
    authToken: accessToken,
    body: payload,
  });
}
