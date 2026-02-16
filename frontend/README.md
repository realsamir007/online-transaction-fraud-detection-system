# Frontend (React + Supabase Auth + Banking Dashboard)

## 1) Configure frontend environment

Create `frontend/.env`:

```bash
cp frontend/.env.example frontend/.env
```

Set these values in `frontend/.env`:

- `VITE_API_BASE_URL=http://127.0.0.1:8001`
- `VITE_SUPABASE_URL=<your-supabase-project-url>`
- `VITE_SUPABASE_ANON_KEY=<your-supabase-anon-key>`

## 2) Configure backend for JWT auth

In backend `.env`:

```env
AUTH_MODE=jwt
ENABLE_DEMO_SEEDING=true
ENABLE_DEMO_MFA_CODE_IN_RESPONSE=true
MFA_SIGNING_SECRET=change-this-mfa-secret
BANKING_ADMIN_API_KEYS=change-this-admin-key
```

Start backend:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

## 3) Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## 4) Implemented user flow

1. User signs in with Supabase Auth.
2. Frontend sends Bearer JWT to backend.
3. Dashboard loads sender account summary and recent transfer history.
4. User validates receiver account (`/banking/validate-receiver`).
5. User initiates transfer (`/banking/transfers/initiate`).
6. Backend auto-computes model features, scores fraud, and applies risk action:
   - `LOW` -> transfer posted (`COMPLETED`)
   - `MEDIUM` -> `MFA_REQUIRED` -> challenge/verify -> posted on successful MFA
   - `HIGH` -> transfer rejected, sender account blocked, `force_logout=true`
7. Optional: click `Load Demo Data` in account summary to seed realistic history/accounts for your logged-in user.
8. Use `Admin Controls` panel to reactivate blocked users by email/user id with admin key.

## 5) Useful backend endpoints used by UI

- `GET /banking/dashboard`
- `GET /banking/transactions?limit=50&offset=0`
- `POST /banking/demo/seed`
- `POST /banking/validate-receiver`
- `POST /banking/transfers/initiate`
- `POST /banking/transfers/{transfer_id}/mfa/challenge`
- `POST /banking/transfers/{transfer_id}/mfa/verify`
- `POST /banking/admin/unblock-user`
