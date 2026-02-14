# Frontend (React + Supabase Auth)

## 1) Configure frontend env

Create `frontend/.env` from template:

```bash
cp frontend/.env.example frontend/.env
```

Set:

- `VITE_API_BASE_URL=http://127.0.0.1:8001`
- `VITE_SUPABASE_URL=<your-supabase-url>`
- `VITE_SUPABASE_ANON_KEY=<your-supabase-anon-key>`

## 2) Configure backend auth mode

In backend `.env`, set:

```env
AUTH_MODE=jwt
```

Keep backend running with:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

## 3) Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

- `http://127.0.0.1:5173`

## 4) Flow

1. Sign up / sign in using Supabase auth credentials.
2. Submit transaction fields.
3. Frontend sends `Authorization: Bearer <access_token>` to backend.
4. Backend validates JWT and returns risk decision.

