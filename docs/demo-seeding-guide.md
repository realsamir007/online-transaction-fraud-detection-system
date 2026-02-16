# Demo Data Seeding Guide

Use this when you want your dashboard to show realistic account balances and transaction history without manual inserts.

## 1) Run SQL setup once in Supabase SQL Editor

Execute these files in order:

1. `/Users/sameerhussain/Desktop/CAP490/project/sql/transactions.sql`
2. `/Users/sameerhussain/Desktop/CAP490/project/sql/banking_phase1.sql`
3. `/Users/sameerhussain/Desktop/CAP490/project/sql/banking_demo_seed.sql`

## 2) Enable demo seed endpoint in backend env

In backend `.env`:

```env
ENABLE_DEMO_SEEDING=true
AUTH_MODE=jwt
```

Restart backend after changing env.

## 3) Seed data from frontend

1. Log in from frontend.
2. Click `Load Demo Data` in the `Account Summary` card.
3. Dashboard refreshes and shows seeded transaction history.

## 4) Seed directly via API (optional)

```bash
curl -X POST "http://127.0.0.1:8001/banking/demo/seed" \
  -H "Authorization: Bearer <your_supabase_access_token>"
```

## What gets seeded

- Sender account is activated and assigned deterministic demo balances/history.
- 3 receiver accounts are created.
- 6 transfer records are added:
  - 4 `COMPLETED`
  - 1 `MFA_REQUIRED`
  - 1 `REJECTED_HIGH_RISK`
