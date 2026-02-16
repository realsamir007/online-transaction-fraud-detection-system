import { useEffect } from "react";
import { AuthPage } from "./features/auth/AuthPage";
import { AdminPanel } from "./features/admin/AdminPanel";
import { UserDashboard } from "./features/dashboard/UserDashboard";
import { validateAdminApiKey } from "./services/adminApi";
import { useAppState } from "./state/AppStateContext";
import { supabase, supabaseConfigError } from "./lib/supabase";

function LoadingScreen() {
  return (
    <main className="app-shell app-shell-centered">
      <section className="status-card">
        <p>Loading secure session...</p>
      </section>
    </main>
  );
}

function ConfigErrorScreen({ message }: { message: string }) {
  return (
    <main className="app-shell app-shell-centered">
      <section className="status-card">
        <h1>Frontend Configuration Error</h1>
        <p className="form-error">{message}</p>
        <p className="ui-field-hint">
          Set <code>VITE_SUPABASE_URL</code> and <code>VITE_SUPABASE_ANON_KEY</code> in frontend env.
        </p>
      </section>
    </main>
  );
}

export default function App() {
  const { state, dispatch } = useAppState();

  useEffect(() => {
    if (!supabase) {
      dispatch({ type: "SET_SESSION_LOADING", payload: false });
      return;
    }

    if (state.role === "admin") {
      dispatch({ type: "SET_SESSION_LOADING", payload: false });
      return;
    }

    void supabase.auth.getSession().then(({ data }) => {
      dispatch({ type: "SET_USER_SESSION", payload: data.session ?? null });
      dispatch({ type: "SET_SESSION_LOADING", payload: false });
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_, nextSession) => {
      dispatch({ type: "SET_USER_SESSION", payload: nextSession ?? null });
      dispatch({ type: "SET_SESSION_LOADING", payload: false });
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, [dispatch, state.role]);

  async function handleUserLogin(email: string, password: string) {
    if (!supabase) {
      throw new Error("Supabase client is not configured.");
    }

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      throw new Error(error.message);
    }
  }

  async function handleSignup(fullName: string, email: string, password: string) {
    if (!supabase) {
      throw new Error("Supabase client is not configured.");
    }

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
        },
      },
    });

    if (error) {
      throw new Error(error.message);
    }
  }

  async function handleAdminLogin(adminApiKey: string) {
    const isValid = await validateAdminApiKey(adminApiKey);
    if (!isValid) {
      throw new Error("Invalid admin API key.");
    }

    dispatch({
      type: "SET_ADMIN_SESSION",
      payload: adminApiKey,
    });
  }

  async function handleLogout() {
    if (state.role === "user" && supabase) {
      await supabase.auth.signOut();
    }
    dispatch({ type: "LOGOUT" });
  }

  if (supabaseConfigError) {
    return <ConfigErrorScreen message={supabaseConfigError} />;
  }

  if (state.sessionLoading && state.role !== "admin") {
    return <LoadingScreen />;
  }

  if (state.role === "admin" && state.adminApiKey) {
    return <AdminPanel adminApiKey={state.adminApiKey} onLogout={() => dispatch({ type: "LOGOUT" })} />;
  }

  if (state.role === "user" && state.session?.access_token) {
    return (
      <UserDashboard
        accessToken={state.session.access_token}
        email={state.session.user.email || "user@intellibank.local"}
        onLogout={handleLogout}
      />
    );
  }

  return <AuthPage onUserLogin={handleUserLogin} onSignup={handleSignup} onAdminLogin={handleAdminLogin} />;
}
