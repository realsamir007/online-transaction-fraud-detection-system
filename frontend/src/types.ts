export type TransactionPayload = {
  step: number;
  amount: number;
  oldbalanceOrg: number;
  newbalanceOrig: number;
  oldbalanceDest: number;
  newbalanceDest: number;
  hour: number;
  is_night: boolean;
  amount_ratio: number;
  sender_balance_change: number;
  receiver_balance_change: number;
  orig_balance_zero: boolean;
  dest_balance_zero: boolean;
  type_TRANSFER: boolean;
};

export type PredictionResponse = {
  fraud_probability: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  action: "APPROVE" | "TRIGGER_MFA" | "BLOCK";
  message: string;
  model_version: string;
};

export type PredictionResult = PredictionResponse & {
  requestId: string;
};

