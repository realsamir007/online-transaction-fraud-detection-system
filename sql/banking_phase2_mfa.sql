CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.transfer_mfa_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_request_id UUID NOT NULL UNIQUE REFERENCES public.transfer_requests(id) ON DELETE CASCADE,
    sender_user_id UUID NOT NULL REFERENCES public.bank_users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    code_length INTEGER NOT NULL CHECK (code_length >= 4 AND code_length <= 10),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'VERIFIED', 'EXPIRED', 'LOCKED')),
    expires_at TIMESTAMP NOT NULL,
    verified_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_transfer_mfa_challenges_updated_at ON public.transfer_mfa_challenges;
CREATE TRIGGER trg_transfer_mfa_challenges_updated_at
BEFORE UPDATE ON public.transfer_mfa_challenges
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE INDEX IF NOT EXISTS idx_transfer_mfa_transfer
ON public.transfer_mfa_challenges (transfer_request_id);

CREATE INDEX IF NOT EXISTS idx_transfer_mfa_status_expires
ON public.transfer_mfa_challenges (status, expires_at);
