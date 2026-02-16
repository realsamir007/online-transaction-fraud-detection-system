# Banking Phase 1 API

All endpoints below require JWT (`Authorization: Bearer <access_token>`).

## 1) Dashboard

`GET /banking/dashboard`

Returns:

- account summary (number, bank code, currency, balance, active status)
- recent transfer history

## 2) Transaction History

`GET /banking/transactions?limit=20&offset=0`

Returns paged history items for incoming/outgoing transfers.

## 3) Receiver Validation

`POST /banking/validate-receiver`

Request:

```json
{
  "receiver_account_number": "1234567890",
  "receiver_bank_code": "CAPBANK001"
}
```

Response includes whether account exists and masked account details.

## 4) Transfer Initiation

`POST /banking/transfers/initiate`

Request:

```json
{
  "receiver_account_number": "1234567890",
  "receiver_bank_code": "CAPBANK001",
  "amount": 1250.0,
  "note": "Invoice settlement"
}
```

Behavior:

- Automatically computes model fields server-side (hour, ratios, balance changes, etc.).
- Runs fraud scoring.
- Applies Phase 1 actions:
  - `LOW` -> immediate posting with atomic debit/credit (`COMPLETED`).
  - `MEDIUM` -> returns `MFA_REQUIRED` (posting deferred).
  - `HIGH` -> returns `REJECTED_HIGH_RISK`, blocks account, `force_logout=true`.

## 5) Demo Data Seeding (Optional, Local/QA)

`POST /banking/demo/seed`

Notes:

- Requires JWT auth.
- Requires backend env: `ENABLE_DEMO_SEEDING=true`.
- Seeds realistic sender/receiver accounts and historical transfer records for the logged-in user.

## 6) MFA Challenge (Phase 2)

`POST /banking/transfers/{transfer_id}/mfa/challenge`

Notes:

- Requires JWT auth.
- Transfer must be owned by sender and in `MFA_REQUIRED` status.
- Generates one-time code challenge with expiry and attempt limits.
- If `ENABLE_DEMO_MFA_CODE_IN_RESPONSE=true`, response includes `demo_code` for local testing.

## 7) MFA Verify + Post

`POST /banking/transfers/{transfer_id}/mfa/verify`

Request:

```json
{
  "code": "123456"
}
```

Behavior:

- Validates challenge status, expiry, and attempt limits.
- On valid code:
  - marks challenge verified
  - transitions transfer to `COMPLETED_PENDING_POSTING`
  - executes atomic posting via `execute_low_risk_transfer`
  - returns `COMPLETED`
- On invalid code:
  - increments attempts
  - locks challenge after max attempts.

## 8) Admin Unblock User

`POST /banking/admin/unblock-user`

Notes:

- Requires admin API key header: `X-Admin-Key`.
- Configure backend env: `BANKING_ADMIN_API_KEYS=<comma-separated-keys>`.

Request by email:

```json
{
  "email": "user@example.com"
}
```

Request by user id:

```json
{
  "user_id": "a4f2d7b2-3d17-4ec8-bf74-1d4d1f88f641"
}
```

Effect:

- Sets `bank_users.status='ACTIVE'`
- Sets `bank_accounts.is_active=true`
- Returns account reactivation result.

## Required SQL Setup

Run these in Supabase SQL editor:

1. `/Users/sameerhussain/Desktop/CAP490/project/sql/transactions.sql`
2. `/Users/sameerhussain/Desktop/CAP490/project/sql/banking_phase1.sql`
3. `/Users/sameerhussain/Desktop/CAP490/project/sql/banking_demo_seed.sql` (if you want one-click demo seeding)
4. `/Users/sameerhussain/Desktop/CAP490/project/sql/banking_phase2_mfa.sql` (required for MFA challenge/verify flow)
