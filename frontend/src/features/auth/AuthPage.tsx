import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import type { AuthView } from "../../types";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { Toggle } from "../../components/ui/Toggle";
import { useToast } from "../../components/ui/Toast";
import { BuildingIcon } from "../../components/icons";

type Props = {
  onUserLogin: (email: string, password: string) => Promise<void>;
  onSignup: (fullName: string, email: string, password: string) => Promise<void>;
  onAdminLogin: (adminApiKey: string) => Promise<void>;
};

export function AuthPage({ onUserLogin, onSignup, onAdminLogin }: Props) {
  const { pushToast } = useToast();

  const [view, setView] = useState<AuthView>("login");
  const [logoFailed, setLogoFailed] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [adminMode, setAdminMode] = useState(false);
  const [adminApiKey, setAdminApiKey] = useState("");

  const [signFullName, setSignFullName] = useState("");
  const [signEmail, setSignEmail] = useState("");
  const [signPassword, setSignPassword] = useState("");
  const [signConfirmPassword, setSignConfirmPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const segmentedOptions = useMemo(
    () => [
      { value: "login" as const, label: "Login" },
      { value: "signup" as const, label: "Signup" },
    ],
    [],
  );

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    if (!loginEmail.trim() || !loginPassword.trim()) {
      setErrorMessage("Email and password are required.");
      return;
    }

    if (adminMode && !adminApiKey.trim()) {
      setErrorMessage("Admin API key is required in admin mode.");
      return;
    }

    setLoading(true);
    try {
      if (adminMode) {
        await onAdminLogin(adminApiKey.trim());
        pushToast("Admin login successful.", "success");
      } else {
        await onUserLogin(loginEmail.trim(), loginPassword);
        pushToast("Logged in successfully.", "success");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Login failed.";
      setErrorMessage(message);
      pushToast(message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleSignupSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    if (!signFullName.trim()) {
      setErrorMessage("Full name is required.");
      return;
    }
    if (!signEmail.trim()) {
      setErrorMessage("Email is required.");
      return;
    }
    if (signPassword.length < 8) {
      setErrorMessage("Password must be at least 8 characters.");
      return;
    }
    if (signPassword !== signConfirmPassword) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await onSignup(signFullName.trim(), signEmail.trim(), signPassword);
      setSuccessMessage("Account created successfully. You can now log in.");
      setView("login");
      setLoginEmail(signEmail.trim());
      setLoginPassword("");
      pushToast("Account created successfully.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sign up failed.";
      setErrorMessage(message);
      pushToast(message, "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell app-shell-centered">
      <Card className="auth-card">
        <div className="auth-brand">
          {logoFailed ? (
            <div className="auth-logo-fallback" aria-label="IntelliBank logo">
              <BuildingIcon width={30} height={30} />
            </div>
          ) : (
            <img
              src="/bank_ai_logo.png"
              alt="IntelliBank logo"
              className="auth-logo"
              onError={() => setLogoFailed(true)}
            />
          )}
          <h1>IntelliBank</h1>
          <p>AI-driven digital banking with built-in fraud defense.</p>
        </div>

        <SegmentedControl value={view} onChange={setView} options={segmentedOptions} />

        {view === "login" ? (
          <form className="auth-form" onSubmit={handleLoginSubmit}>
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              value={loginEmail}
              onChange={(event) => setLoginEmail(event.target.value)}
              placeholder="name@bank.com"
              required
              disabled={loading}
            />
            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              placeholder="Enter password"
              required
              disabled={loading}
            />

            <Toggle
              label="Are you Admin?"
              checked={adminMode}
              onChange={(event) => setAdminMode(event.target.checked)}
              disabled={loading}
            />

            {adminMode ? (
              <Input
                label="Admin API Key"
                type="password"
                value={adminApiKey}
                onChange={(event) => setAdminApiKey(event.target.value)}
                placeholder="X-Admin-Key"
                required
                disabled={loading}
              />
            ) : null}

            <Button type="submit" loading={loading} fullWidth>
              Login
            </Button>
          </form>
        ) : (
          <form className="auth-form" onSubmit={handleSignupSubmit}>
            <Input
              label="Full Name"
              type="text"
              autoComplete="name"
              value={signFullName}
              onChange={(event) => setSignFullName(event.target.value)}
              placeholder="John Doe"
              required
              disabled={loading}
            />
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              value={signEmail}
              onChange={(event) => setSignEmail(event.target.value)}
              placeholder="name@bank.com"
              required
              disabled={loading}
            />
            <Input
              label="Password"
              type="password"
              autoComplete="new-password"
              value={signPassword}
              onChange={(event) => setSignPassword(event.target.value)}
              placeholder="Minimum 8 characters"
              required
              disabled={loading}
            />
            <Input
              label="Confirm Password"
              type="password"
              autoComplete="new-password"
              value={signConfirmPassword}
              onChange={(event) => setSignConfirmPassword(event.target.value)}
              placeholder="Confirm your password"
              required
              disabled={loading}
            />
            <Button type="submit" loading={loading} fullWidth>
              Create Account
            </Button>
          </form>
        )}

        {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
        {successMessage ? <p className="form-success">{successMessage}</p> : null}
      </Card>
    </main>
  );
}
