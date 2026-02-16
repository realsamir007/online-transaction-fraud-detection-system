CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION public.stable_uuid_from_text(p_input TEXT)
RETURNS UUID
LANGUAGE SQL
IMMUTABLE
AS $$
SELECT (
    substr(md5(p_input), 1, 8) || '-' ||
    substr(md5(p_input), 9, 4) || '-' ||
    substr(md5(p_input), 13, 4) || '-' ||
    substr(md5(p_input), 17, 4) || '-' ||
    substr(md5(p_input), 21, 12)
)::uuid;
$$;

CREATE OR REPLACE FUNCTION public.stable_account_number_from_text(p_input TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
SELECT lpad(translate(substr(md5(p_input), 1, 10), 'abcdef', '123456'), 10, '0');
$$;

CREATE OR REPLACE FUNCTION public.seed_demo_banking_data_for_user(
    p_user_id UUID,
    p_email TEXT DEFAULT NULL,
    p_bank_code TEXT DEFAULT 'CAPBANK001'
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_now TIMESTAMP := NOW();
    v_seed_prefix TEXT := 'seed-demo-' || replace(substr(p_user_id::text, 1, 8), '-', '');
    v_sender_email TEXT := COALESCE(NULLIF(trim(p_email), ''), 'demo-user@capbank.local');

    v_sender_account_id UUID;
    v_sender_account_number TEXT;

    v_receiver_1_user_id UUID := public.stable_uuid_from_text(p_user_id::text || ':receiver:alice');
    v_receiver_2_user_id UUID := public.stable_uuid_from_text(p_user_id::text || ':receiver:bob');
    v_receiver_3_user_id UUID := public.stable_uuid_from_text(p_user_id::text || ':receiver:charlie');

    v_receiver_1_account_id UUID;
    v_receiver_2_account_id UUID;
    v_receiver_3_account_id UUID;

    v_receiver_1_account_number TEXT := public.stable_account_number_from_text(p_user_id::text || ':acct:alice');
    v_receiver_2_account_number TEXT := public.stable_account_number_from_text(p_user_id::text || ':acct:bob');
    v_receiver_3_account_number TEXT := public.stable_account_number_from_text(p_user_id::text || ':acct:charlie');

    v_sender_start_balance NUMERIC(18, 2) := 25000.00;
    v_receiver_1_start_balance NUMERIC(18, 2) := 42000.00;
    v_receiver_2_start_balance NUMERIC(18, 2) := 18000.00;
    v_receiver_3_start_balance NUMERIC(18, 2) := 36500.00;

    v_t1_amount NUMERIC(18, 2) := 1200.00;
    v_t2_amount NUMERIC(18, 2) := 750.00;
    v_t3_amount NUMERIC(18, 2) := 3150.00;
    v_t4_amount NUMERIC(18, 2) := 500.00;
    v_t5_amount NUMERIC(18, 2) := 9800.00;
    v_t6_amount NUMERIC(18, 2) := 15000.00;

    v_t1_id UUID := public.stable_uuid_from_text(v_seed_prefix || ':t1');
    v_t2_id UUID := public.stable_uuid_from_text(v_seed_prefix || ':t2');
    v_t3_id UUID := public.stable_uuid_from_text(v_seed_prefix || ':t3');
    v_t4_id UUID := public.stable_uuid_from_text(v_seed_prefix || ':t4');
    v_t5_id UUID := public.stable_uuid_from_text(v_seed_prefix || ':t5');
    v_t6_id UUID := public.stable_uuid_from_text(v_seed_prefix || ':t6');

    v_sender_final_balance NUMERIC(18, 2);
BEGIN
    INSERT INTO public.bank_users (
        id,
        email,
        full_name,
        status,
        created_at,
        updated_at
    ) VALUES (
        p_user_id,
        v_sender_email,
        COALESCE(NULLIF(initcap(replace(split_part(v_sender_email, '@', 1), '.', ' ')), ''), 'Demo Sender'),
        'ACTIVE',
        v_now,
        v_now
    )
    ON CONFLICT (id) DO UPDATE SET
        email = COALESCE(EXCLUDED.email, public.bank_users.email),
        status = 'ACTIVE',
        updated_at = v_now;

    SELECT id, account_number
    INTO v_sender_account_id, v_sender_account_number
    FROM public.bank_accounts
    WHERE user_id = p_user_id
    LIMIT 1;

    IF v_sender_account_id IS NULL THEN
        v_sender_account_number := public.stable_account_number_from_text(p_user_id::text || ':acct:sender');
        INSERT INTO public.bank_accounts (
            user_id,
            account_number,
            bank_code,
            currency,
            balance,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            p_user_id,
            v_sender_account_number,
            p_bank_code,
            'USD',
            v_sender_start_balance,
            TRUE,
            v_now,
            v_now
        )
        RETURNING id, account_number INTO v_sender_account_id, v_sender_account_number;
    ELSE
        UPDATE public.bank_accounts
        SET
            bank_code = p_bank_code,
            currency = 'USD',
            is_active = TRUE,
            updated_at = v_now
        WHERE id = v_sender_account_id;
    END IF;

    INSERT INTO public.bank_users (id, email, full_name, status, created_at, updated_at)
    VALUES (v_receiver_1_user_id, 'alice.receiver@capbank.local', 'Alice Receiver', 'ACTIVE', v_now, v_now)
    ON CONFLICT (id) DO UPDATE SET status = 'ACTIVE', updated_at = v_now;

    INSERT INTO public.bank_users (id, email, full_name, status, created_at, updated_at)
    VALUES (v_receiver_2_user_id, 'bob.receiver@capbank.local', 'Bob Receiver', 'ACTIVE', v_now, v_now)
    ON CONFLICT (id) DO UPDATE SET status = 'ACTIVE', updated_at = v_now;

    INSERT INTO public.bank_users (id, email, full_name, status, created_at, updated_at)
    VALUES (v_receiver_3_user_id, 'charlie.receiver@capbank.local', 'Charlie Receiver', 'ACTIVE', v_now, v_now)
    ON CONFLICT (id) DO UPDATE SET status = 'ACTIVE', updated_at = v_now;

    INSERT INTO public.bank_accounts (
        user_id,
        account_number,
        bank_code,
        currency,
        balance,
        is_active,
        created_at,
        updated_at
    ) VALUES (
        v_receiver_1_user_id,
        v_receiver_1_account_number,
        p_bank_code,
        'USD',
        v_receiver_1_start_balance,
        TRUE,
        v_now,
        v_now
    )
    ON CONFLICT (user_id) DO UPDATE SET
        bank_code = EXCLUDED.bank_code,
        currency = EXCLUDED.currency,
        is_active = TRUE,
        updated_at = v_now;

    INSERT INTO public.bank_accounts (
        user_id,
        account_number,
        bank_code,
        currency,
        balance,
        is_active,
        created_at,
        updated_at
    ) VALUES (
        v_receiver_2_user_id,
        v_receiver_2_account_number,
        p_bank_code,
        'USD',
        v_receiver_2_start_balance,
        TRUE,
        v_now,
        v_now
    )
    ON CONFLICT (user_id) DO UPDATE SET
        bank_code = EXCLUDED.bank_code,
        currency = EXCLUDED.currency,
        is_active = TRUE,
        updated_at = v_now;

    INSERT INTO public.bank_accounts (
        user_id,
        account_number,
        bank_code,
        currency,
        balance,
        is_active,
        created_at,
        updated_at
    ) VALUES (
        v_receiver_3_user_id,
        v_receiver_3_account_number,
        p_bank_code,
        'USD',
        v_receiver_3_start_balance,
        TRUE,
        v_now,
        v_now
    )
    ON CONFLICT (user_id) DO UPDATE SET
        bank_code = EXCLUDED.bank_code,
        currency = EXCLUDED.currency,
        is_active = TRUE,
        updated_at = v_now;

    SELECT id INTO v_receiver_1_account_id FROM public.bank_accounts WHERE user_id = v_receiver_1_user_id LIMIT 1;
    SELECT id INTO v_receiver_2_account_id FROM public.bank_accounts WHERE user_id = v_receiver_2_user_id LIMIT 1;
    SELECT id INTO v_receiver_3_account_id FROM public.bank_accounts WHERE user_id = v_receiver_3_user_id LIMIT 1;

    DELETE FROM public.account_ledger_entries
    WHERE transfer_request_id IN (
        SELECT id
        FROM public.transfer_requests
        WHERE request_id LIKE v_seed_prefix || ':%'
    );

    DELETE FROM public.transfer_requests
    WHERE request_id LIKE v_seed_prefix || ':%';

    UPDATE public.bank_users SET status = 'ACTIVE', updated_at = v_now WHERE id = p_user_id;
    UPDATE public.bank_accounts SET balance = v_sender_start_balance, is_active = TRUE, updated_at = v_now WHERE id = v_sender_account_id;
    UPDATE public.bank_accounts SET balance = v_receiver_1_start_balance, is_active = TRUE, updated_at = v_now WHERE id = v_receiver_1_account_id;
    UPDATE public.bank_accounts SET balance = v_receiver_2_start_balance, is_active = TRUE, updated_at = v_now WHERE id = v_receiver_2_account_id;
    UPDATE public.bank_accounts SET balance = v_receiver_3_start_balance, is_active = TRUE, updated_at = v_now WHERE id = v_receiver_3_account_id;

    INSERT INTO public.transfer_requests (
        id,
        sender_user_id,
        receiver_user_id,
        sender_account_id,
        receiver_account_id,
        sender_account_number,
        sender_bank_code,
        receiver_account_number,
        receiver_bank_code,
        amount,
        note,
        status,
        risk_level,
        action,
        fraud_probability,
        model_version,
        request_id,
        created_at,
        updated_at
    ) VALUES
    (
        v_t1_id,
        p_user_id,
        v_receiver_1_user_id,
        v_sender_account_id,
        v_receiver_1_account_id,
        v_sender_account_number,
        p_bank_code,
        v_receiver_1_account_number,
        p_bank_code,
        v_t1_amount,
        'Utility payment',
        'COMPLETED',
        'LOW',
        'APPROVE',
        0.07,
        'random_forest_v1',
        v_seed_prefix || ':t1',
        v_now - INTERVAL '6 days',
        v_now - INTERVAL '6 days'
    ),
    (
        v_t2_id,
        v_receiver_1_user_id,
        p_user_id,
        v_receiver_1_account_id,
        v_sender_account_id,
        v_receiver_1_account_number,
        p_bank_code,
        v_sender_account_number,
        p_bank_code,
        v_t2_amount,
        'Partial refund',
        'COMPLETED',
        'LOW',
        'APPROVE',
        0.11,
        'random_forest_v1',
        v_seed_prefix || ':t2',
        v_now - INTERVAL '5 days',
        v_now - INTERVAL '5 days'
    ),
    (
        v_t3_id,
        p_user_id,
        v_receiver_2_user_id,
        v_sender_account_id,
        v_receiver_2_account_id,
        v_sender_account_number,
        p_bank_code,
        v_receiver_2_account_number,
        p_bank_code,
        v_t3_amount,
        'Monthly rent',
        'COMPLETED',
        'LOW',
        'APPROVE',
        0.18,
        'random_forest_v1',
        v_seed_prefix || ':t3',
        v_now - INTERVAL '3 days',
        v_now - INTERVAL '3 days'
    ),
    (
        v_t4_id,
        v_receiver_3_user_id,
        p_user_id,
        v_receiver_3_account_id,
        v_sender_account_id,
        v_receiver_3_account_number,
        p_bank_code,
        v_sender_account_number,
        p_bank_code,
        v_t4_amount,
        'Cashback reward',
        'COMPLETED',
        'LOW',
        'APPROVE',
        0.21,
        'random_forest_v1',
        v_seed_prefix || ':t4',
        v_now - INTERVAL '1 day',
        v_now - INTERVAL '1 day'
    ),
    (
        v_t5_id,
        p_user_id,
        v_receiver_3_user_id,
        v_sender_account_id,
        v_receiver_3_account_id,
        v_sender_account_number,
        p_bank_code,
        v_receiver_3_account_number,
        p_bank_code,
        v_t5_amount,
        'Unusual large transfer',
        'MFA_REQUIRED',
        'MEDIUM',
        'TRIGGER_MFA',
        0.62,
        'random_forest_v1',
        v_seed_prefix || ':t5',
        v_now - INTERVAL '12 hours',
        v_now - INTERVAL '12 hours'
    ),
    (
        v_t6_id,
        p_user_id,
        v_receiver_2_user_id,
        v_sender_account_id,
        v_receiver_2_account_id,
        v_sender_account_number,
        p_bank_code,
        v_receiver_2_account_number,
        p_bank_code,
        v_t6_amount,
        'High-risk flagged transfer',
        'REJECTED_HIGH_RISK',
        'HIGH',
        'BLOCK',
        0.91,
        'random_forest_v1',
        v_seed_prefix || ':t6',
        v_now - INTERVAL '2 hours',
        v_now - INTERVAL '2 hours'
    );

    INSERT INTO public.account_ledger_entries (
        account_id,
        transfer_request_id,
        entry_type,
        amount,
        balance_before,
        balance_after,
        description,
        created_at
    ) VALUES
    (
        v_sender_account_id,
        v_t1_id,
        'DEBIT',
        v_t1_amount,
        25000.00,
        23800.00,
        'Utility payment',
        v_now - INTERVAL '6 days'
    ),
    (
        v_receiver_1_account_id,
        v_t1_id,
        'CREDIT',
        v_t1_amount,
        42000.00,
        43200.00,
        'Utility payment',
        v_now - INTERVAL '6 days'
    ),
    (
        v_receiver_1_account_id,
        v_t2_id,
        'DEBIT',
        v_t2_amount,
        43200.00,
        42450.00,
        'Partial refund',
        v_now - INTERVAL '5 days'
    ),
    (
        v_sender_account_id,
        v_t2_id,
        'CREDIT',
        v_t2_amount,
        23800.00,
        24550.00,
        'Partial refund',
        v_now - INTERVAL '5 days'
    ),
    (
        v_sender_account_id,
        v_t3_id,
        'DEBIT',
        v_t3_amount,
        24550.00,
        21400.00,
        'Monthly rent',
        v_now - INTERVAL '3 days'
    ),
    (
        v_receiver_2_account_id,
        v_t3_id,
        'CREDIT',
        v_t3_amount,
        18000.00,
        21150.00,
        'Monthly rent',
        v_now - INTERVAL '3 days'
    ),
    (
        v_receiver_3_account_id,
        v_t4_id,
        'DEBIT',
        v_t4_amount,
        36500.00,
        36000.00,
        'Cashback reward',
        v_now - INTERVAL '1 day'
    ),
    (
        v_sender_account_id,
        v_t4_id,
        'CREDIT',
        v_t4_amount,
        21400.00,
        21900.00,
        'Cashback reward',
        v_now - INTERVAL '1 day'
    );

    v_sender_final_balance := 21900.00;

    UPDATE public.bank_accounts SET balance = 21900.00, updated_at = v_now WHERE id = v_sender_account_id;
    UPDATE public.bank_accounts SET balance = 42450.00, updated_at = v_now WHERE id = v_receiver_1_account_id;
    UPDATE public.bank_accounts SET balance = 21150.00, updated_at = v_now WHERE id = v_receiver_2_account_id;
    UPDATE public.bank_accounts SET balance = 36000.00, updated_at = v_now WHERE id = v_receiver_3_account_id;

    RETURN jsonb_build_object(
        'seeded', TRUE,
        'message', 'Demo banking data seeded for this user.',
        'sender_account_number', v_sender_account_number,
        'bank_code', p_bank_code,
        'sender_balance', v_sender_final_balance,
        'transfers_seeded', 6,
        'completed_transfers', 4,
        'pending_mfa_transfers', 1,
        'blocked_transfers', 1
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.seed_demo_banking_data_by_email(
    p_email TEXT,
    p_bank_code TEXT DEFAULT 'CAPBANK001'
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id UUID;
BEGIN
    SELECT id
    INTO v_user_id
    FROM auth.users
    WHERE lower(email) = lower(trim(p_email))
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'No auth user found for email: %', p_email;
    END IF;

    RETURN public.seed_demo_banking_data_for_user(v_user_id, p_email, p_bank_code);
END;
$$;
