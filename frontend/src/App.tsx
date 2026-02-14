import { useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import AuthPanel from "./components/AuthPanel";
import PredictionResultCard from "./components/PredictionResultCard";
import TransactionForm from "./components/TransactionForm";
import { predictTransaction } from "./lib/api";
import { supabase, supabaseConfigError } from "./lib/supabase";
import type { PredictionResult, TransactionPayload } from "./types";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const [predictionResult, setPredictionResult] = useState<PredictionResult | null>(null);
  const [predictionError, setPredictionError] = useState("");
  const [predictionLoading, setPredictionLoading] = useState(false);

  const apiBaseUrl = useMemo(() => import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001", []);

  useEffect(() => {
    if (!supabase) {
      setSessionLoading(false);
      return;
    }

    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session ?? null);
      setSessionLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_, nextSession) => {
      setSession(nextSession ?? null);
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  async function handleSignIn() {
    if (!supabase) {
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    setAuthMessage("");

    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      setAuthError(error.message);
    } else {
      setAuthMessage("Signed in successfully.");
    }
    setAuthLoading(false);
  }

  async function handleSignUp() {
    if (!supabase) {
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    setAuthMessage("");

    const { error } = await supabase.auth.signUp({ email, password });
    if (error) {
      setAuthError(error.message);
    } else {
      setAuthMessage("Sign-up successful. Check email if confirmation is enabled.");
    }
    setAuthLoading(false);
  }

  async function handleSignOut() {
    if (!supabase) {
      return;
    }
    await supabase.auth.signOut();
    setPredictionResult(null);
    setPredictionError("");
  }

  async function handlePredict(payload: TransactionPayload) {
    if (!session?.access_token) {
      setPredictionError("No active user session. Sign in again.");
      return;
    }

    setPredictionLoading(true);
    setPredictionError("");
    try {
      const result = await predictTransaction(payload, session.access_token);
      setPredictionResult(result);
    } catch (error) {
      setPredictionResult(null);
      setPredictionError(error instanceof Error ? error.message : "Prediction request failed.");
    } finally {
      setPredictionLoading(false);
    }
  }

  if (supabaseConfigError) {
    return (
      <main className="layout">
        <section className="panel error-panel">
          <h1>Fraud Detection Console</h1>
          <p className="error">{supabaseConfigError}</p>
          <p className="muted">
            Copy <code>frontend/.env.example</code> to <code>frontend/.env</code> and set values, then restart
            Vite.
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="layout">
      <header className="hero">
        <h1>Fraud Detection Console</h1>
        <p>JWT-authenticated scoring client for the FastAPI fraud service.</p>
        <div className="hero-meta">
          <span>API: {apiBaseUrl}</span>
          <span>Auth Mode: JWT / Bearer</span>
        </div>
      </header>

      {sessionLoading ? (
        <section className="panel">
          <p className="muted">Loading session...</p>
        </section>
      ) : !session ? (
        <AuthPanel
          email={email}
          password={password}
          setEmail={setEmail}
          setPassword={setPassword}
          authError={authError}
          authMessage={authMessage}
          loading={authLoading}
          onSignIn={handleSignIn}
          onSignUp={handleSignUp}
        />
      ) : (
        <section className="workspace">
          <div className="session-row">
            <div>
              <p className="muted">Signed in as</p>
              <strong>{session.user.email}</strong>
            </div>
            <button className="secondary-btn" onClick={handleSignOut}>
              Sign Out
            </button>
          </div>

          <div className="content-grid">
            <TransactionForm disabled={predictionLoading} onSubmit={handlePredict} />
            <PredictionResultCard result={predictionResult} error={predictionError} isLoading={predictionLoading} />
          </div>
        </section>
      )}
    </main>
  );
}

