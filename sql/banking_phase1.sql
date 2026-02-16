CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS public.bank_users (
    id UUID PRIMARY KEY,
    email TEXT,
    full_name TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'BLOCKED')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.bank_users(id) ON DELETE CASCADE,
    account_number TEXT NOT NULL UNIQUE,
    bank_code TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    balance NUMERIC(18, 2) NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_bank_accounts_user UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS public.transfer_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_user_id UUID NOT NULL REFERENCES public.bank_users(id),
    receiver_user_id UUID NOT NULL REFERENCES public.bank_users(id),
    sender_account_id UUID NOT NULL REFERENCES public.bank_accounts(id),
    receiver_account_id UUID NOT NULL REFERENCES public.bank_accounts(id),
    sender_account_number TEXT NOT NULL,
    sender_bank_code TEXT NOT NULL,
    receiver_account_number TEXT NOT NULL,
    receiver_bank_code TEXT NOT NULL,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount > 0),
    note TEXT,
    status TEXT NOT NULL CHECK (
        status IN (
            'COMPLETED_PENDING_POSTING',
            'COMPLETED',
            'MFA_REQUIRED',
            'REJECTED_HIGH_RISK',
            'REJECTED_INSUFFICIENT_FUNDS',
            'FAILED'
        )
    ),
    risk_level TEXT,
    action TEXT,
    fraud_probability NUMERIC,
    model_version TEXT,
    request_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.account_ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES public.bank_accounts(id),
    transfer_request_id UUID NOT NULL REFERENCES public.transfer_requests(id),
    entry_type TEXT NOT NULL CHECK (entry_type IN ('DEBIT', 'CREDIT')),
    amount NUMERIC(18, 2) NOT NULL CHECK (amount > 0),
    balance_before NUMERIC(18, 2) NOT NULL,
    balance_after NUMERIC(18, 2) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_bank_users_updated_at ON public.bank_users;
CREATE TRIGGER trg_bank_users_updated_at
BEFORE UPDATE ON public.bank_users
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_bank_accounts_updated_at ON public.bank_accounts;
CREATE TRIGGER trg_bank_accounts_updated_at
BEFORE UPDATE ON public.bank_accounts
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_transfer_requests_updated_at ON public.transfer_requests;
CREATE TRIGGER trg_transfer_requests_updated_at
BEFORE UPDATE ON public.transfer_requests
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE INDEX IF NOT EXISTS idx_bank_accounts_bank_lookup
ON public.bank_accounts (bank_code, account_number);

CREATE INDEX IF NOT EXISTS idx_transfer_requests_sender_created
ON public.transfer_requests (sender_account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_transfer_requests_receiver_created
ON public.transfer_requests (receiver_account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ledger_account_created
ON public.account_ledger_entries (account_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.execute_low_risk_transfer(
    p_transfer_request_id UUID,
    p_sender_account_id UUID,
    p_receiver_account_id UUID,
    p_amount NUMERIC,
    p_note TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_transfer public.transfer_requests%ROWTYPE;
    v_sender_balance NUMERIC(18, 2);
    v_receiver_balance NUMERIC(18, 2);
    v_sender_after NUMERIC(18, 2);
    v_receiver_after NUMERIC(18, 2);
BEGIN
    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be greater than zero.';
    END IF;

    SELECT *
    INTO v_transfer
    FROM public.transfer_requests
    WHERE id = p_transfer_request_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transfer request not found.';
    END IF;

    IF v_transfer.status <> 'COMPLETED_PENDING_POSTING' THEN
        RAISE EXCEPTION 'Transfer request is not in postable state.';
    END IF;

    IF v_transfer.sender_account_id <> p_sender_account_id
       OR v_transfer.receiver_account_id <> p_receiver_account_id THEN
        RAISE EXCEPTION 'Transfer request/account mismatch.';
    END IF;

    SELECT balance
    INTO v_sender_balance
    FROM public.bank_accounts
    WHERE id = p_sender_account_id
    FOR UPDATE;

    SELECT balance
    INTO v_receiver_balance
    FROM public.bank_accounts
    WHERE id = p_receiver_account_id
    FOR UPDATE;

    IF v_sender_balance IS NULL OR v_receiver_balance IS NULL THEN
        RAISE EXCEPTION 'One or more accounts were not found.';
    END IF;

    IF v_sender_balance < p_amount THEN
        UPDATE public.transfer_requests
        SET status = 'REJECTED_INSUFFICIENT_FUNDS'
        WHERE id = p_transfer_request_id;
        RAISE EXCEPTION 'Insufficient sender balance.';
    END IF;

    v_sender_after := v_sender_balance - p_amount;
    v_receiver_after := v_receiver_balance + p_amount;

    UPDATE public.bank_accounts
    SET balance = v_sender_after
    WHERE id = p_sender_account_id;

    UPDATE public.bank_accounts
    SET balance = v_receiver_after
    WHERE id = p_receiver_account_id;

    INSERT INTO public.account_ledger_entries (
        account_id,
        transfer_request_id,
        entry_type,
        amount,
        balance_before,
        balance_after,
        description
    ) VALUES (
        p_sender_account_id,
        p_transfer_request_id,
        'DEBIT',
        p_amount,
        v_sender_balance,
        v_sender_after,
        COALESCE(p_note, 'Transfer debit')
    );

    INSERT INTO public.account_ledger_entries (
        account_id,
        transfer_request_id,
        entry_type,
        amount,
        balance_before,
        balance_after,
        description
    ) VALUES (
        p_receiver_account_id,
        p_transfer_request_id,
        'CREDIT',
        p_amount,
        v_receiver_balance,
        v_receiver_after,
        COALESCE(p_note, 'Transfer credit')
    );

    UPDATE public.transfer_requests
    SET status = 'COMPLETED'
    WHERE id = p_transfer_request_id;

    RETURN jsonb_build_object(
        'transfer_request_id', p_transfer_request_id,
        'sender_balance_before', v_sender_balance,
        'sender_balance_after', v_sender_after,
        'receiver_balance_before', v_receiver_balance,
        'receiver_balance_after', v_receiver_after
    );
EXCEPTION
    WHEN OTHERS THEN
        UPDATE public.transfer_requests
        SET status = CASE
            WHEN status = 'COMPLETED_PENDING_POSTING' THEN 'FAILED'
            ELSE status
        END
        WHERE id = p_transfer_request_id;
        RAISE;
END;
$$;

