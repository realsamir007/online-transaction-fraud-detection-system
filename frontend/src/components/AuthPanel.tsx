type Props = {
  email: string;
  password: string;
  setEmail: (value: string) => void;
  setPassword: (value: string) => void;
  authError: string;
  authMessage: string;
  loading: boolean;
  onSignIn: () => Promise<void>;
  onSignUp: () => Promise<void>;
};

export default function AuthPanel({
  email,
  password,
  setEmail,
  setPassword,
  authError,
  authMessage,
  loading,
  onSignIn,
  onSignUp,
}: Props) {
  return (
    <section className="panel auth-panel">
      <div className="panel-header">
        <h2>Authenticate</h2>
        <p>Sign in with Supabase user credentials to get a JWT.</p>
      </div>

      <label className="field">
        <span>Email</span>
        <input
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          required
          disabled={loading}
        />
      </label>

      <label className="field">
        <span>Password</span>
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="••••••••"
          required
          disabled={loading}
        />
      </label>

      <div className="auth-actions">
        <button className="primary-btn" onClick={onSignIn} disabled={loading || !email || !password}>
          {loading ? "Signing in..." : "Sign In"}
        </button>
        <button className="secondary-btn" onClick={onSignUp} disabled={loading || !email || !password}>
          Sign Up
        </button>
      </div>

      {authError && <p className="error">{authError}</p>}
      {authMessage && <p className="success">{authMessage}</p>}
    </section>
  );
}

