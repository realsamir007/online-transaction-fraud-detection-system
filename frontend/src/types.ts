export type AccountSummary = {
  account_id: string;
  account_number: string;
  bank_code: string;
  currency: string;
  balance: number;
  is_active: boolean;
};

export type TransferHistoryItem = {
  transfer_id: string;
  direction: "INCOMING" | "OUTGOING";
  counterparty_account_number: string;
  counterparty_bank_code: string;
  amount: number;
  status: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | null;
  action: "APPROVE" | "TRIGGER_MFA" | "BLOCK" | null;
  note: string | null;
  created_at: string;
};

export type DashboardResponse = {
  account: AccountSummary;
  recent_transactions: TransferHistoryItem[];
};

export type TransactionHistoryResponse = {
  items: TransferHistoryItem[];
  limit: number;
  offset: number;
};

export type ReceiverValidationRequest = {
  receiver_account_number: string;
  receiver_bank_code: string;
};

export type ReceiverValidationResponse = {
  exists: boolean;
  account_holder: string | null;
  account_number_masked: string | null;
  bank_code: string | null;
  message: string;
};

export type InitiateTransferRequest = {
  receiver_account_number: string;
  receiver_bank_code: string;
  amount: number;
  note?: string;
};

export type TransferInitiateResponse = {
  transfer_id: string;
  status: string;
  fraud_probability: number | null;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | null;
  action: "APPROVE" | "TRIGGER_MFA" | "BLOCK" | null;
  message: string;
  mfa_required: boolean;
  force_logout: boolean;
  sender_balance: number | null;
  receiver_balance: number | null;
  request_id: string;
};

export type TransferMfaChallengeResponse = {
  transfer_id: string;
  status: string;
  mfa_required: boolean;
  message: string;
  expires_at: string;
  remaining_attempts: number;
  request_id: string;
  demo_code: string | null;
};

export type TransferMfaVerifyRequest = {
  code: string;
};

export type DemoSeedResponse = {
  seeded: boolean;
  message: string;
  sender_account_number: string;
  bank_code: string;
  sender_balance: number;
  transfers_seeded: number;
  completed_transfers: number;
  pending_mfa_transfers: number;
  blocked_transfers: number;
};

export type AdminUnblockUserRequest = {
  user_id?: string;
  email?: string;
};

export type AdminUnblockUserResponse = {
  user_id: string;
  email: string | null;
  account_id: string;
  account_number: string;
  bank_code: string;
  user_status: string;
  account_active: boolean;
  message: string;
};
