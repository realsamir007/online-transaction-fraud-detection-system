# E-Banking Dashboard + Fraud-Orchestrated Transfer Flow

## Scope Locked From Product Discussion

The system must evolve from a raw fraud-scoring form into a practical e-banking experience.

### User Journey

1. User logs in with credentials and lands on an e-banking dashboard.
2. Dashboard shows:
   - Current account balance
   - Historical transactions
3. User initiates money transfer by entering receiver bank/account details.
4. System validates whether receiver account exists.
5. Fraud model runs automatically during transfer evaluation.
6. Decision outcomes:
   - LOW risk: transfer approved, sender debited, receiver credited.
   - MEDIUM risk: challenge user with re-authentication (password/OTP), then proceed on success.
   - HIGH risk: block account, force logout, redirect to home/login page.

### Feature Engineering Must Be Automatic

The frontend should only collect practical banking inputs. These model fields must be computed server-side:

- hour
- is_night
- amount_ratio
- sender_balance_change
- receiver_balance_change
- orig_balance_zero
- dest_balance_zero

### Data/Consistency Requirements

- Transfer posting must be atomic (no partial debit/credit).
- Fraud decision, transaction log, and account changes must be consistent.
- Risk/action decisions should remain auditable.

---

## Delivery Plan (Step-by-Step)

### Phase 1: Core Banking Data Model + APIs

- Status: Implemented (backend + SQL + automated tests).
- Added tables: user profile status, bank accounts, transfer_requests, account_ledger_entries.
- Added backend APIs:
  - dashboard summary
  - transaction history
  - receiver account validation
  - transfer initiation
- Computed fraud model features server-side from transfer intent + account state.

### Phase 2: Fraud-Orchestrated Transfer Engine

- Status: Implemented (backend endpoints + SQL + automated tests).
- Integrated fraud inference in transfer initiation.
- Implemented risk actions:
  - LOW: post transfer immediately
  - MEDIUM: create pending transfer + MFA challenge/verify flow
  - HIGH: mark account blocked + deny + require fresh login flow
- Added MFA endpoints:
  - create challenge
  - verify code and post transfer atomically

### Phase 3: Frontend E-Banking UX

- Build authenticated dashboard UI:
  - balance card
  - transaction history table
  - transfer form (receiver validation + transfer submit)
- Added optional one-click demo data seeding action for local/QA onboarding.
- Handle risk outcomes in UX:
  - LOW success receipt
  - MEDIUM MFA confirmation screen
  - HIGH blocked state and redirect to login

### Phase 4: Security + Reliability

- Enforce JWT-only auth for frontend backend calls.
- Add secure MFA flow (OTP/TOTP) for medium risk.
- Add ledger/transfer idempotency and race-condition protections.
- Add E2E tests for transfer lifecycle and risk branches.

---

## Default Assumptions (Unless Changed)

- Receiver validation is against internal bank accounts in this system (no external bank API yet).
- Medium-risk challenge uses OTP first (expand to stronger MFA later).
- Blocked account status is enforced server-side on all protected endpoints.
