CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step INTEGER NOT NULL,
    amount NUMERIC NOT NULL,
    "oldbalanceOrg" NUMERIC NOT NULL,
    "newbalanceOrig" NUMERIC NOT NULL,
    "oldbalanceDest" NUMERIC NOT NULL,
    "newbalanceDest" NUMERIC NOT NULL,
    hour INTEGER NOT NULL,
    "is_night" BOOLEAN NOT NULL,
    "amount_ratio" NUMERIC NOT NULL,
    "sender_balance_change" NUMERIC NOT NULL,
    "receiver_balance_change" NUMERIC NOT NULL,
    "orig_balance_zero" BOOLEAN NOT NULL,
    "dest_balance_zero" BOOLEAN NOT NULL,
    "type_TRANSFER" BOOLEAN NOT NULL,
    "fraud_probability" NUMERIC NOT NULL,
    "risk_level" TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON public.transactions (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_risk_level ON public.transactions ("risk_level");
