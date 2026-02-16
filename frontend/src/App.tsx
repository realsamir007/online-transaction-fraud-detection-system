import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import AuthPanel from "./components/AuthPanel";
import {
  adminUnblockUser,
  fetchDashboard,
  fetchTransactionHistory,
  initiateTransfer,
  requestTransferMfaChallenge,
  seedDemoBankingData,
  validateReceiver,
  verifyTransferMfa,
} from "./lib/api";
import { supabase, supabaseConfigError } from "./lib/supabase";
import type {
  AdminUnblockUserResponse,
  DashboardResponse,
  InitiateTransferRequest,
  ReceiverValidationResponse,
  TransferHistoryItem,
  TransferInitiateResponse,
  TransferMfaChallengeResponse,
} from "./types";

function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function riskClassName(riskLevel: string | null): string {
  if (riskLevel === "HIGH") {
    return "risk-chip risk-high";
  }
  if (riskLevel === "MEDIUM") {
    return "risk-chip risk-medium";
  }
  if (riskLevel === "LOW") {
    return "risk-chip risk-low";
  }
  return "risk-chip risk-neutral";
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [history, setHistory] = useState<TransferHistoryItem[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState("");
  const [seedLoading, setSeedLoading] = useState(false);
  const [seedMessage, setSeedMessage] = useState("");

  const [receiverBankCode, setReceiverBankCode] = useState("CAPBANK001");
  const [receiverAccountNumber, setReceiverAccountNumber] = useState("");
  const [amount, setAmount] = useState("100");
  const [note, setNote] = useState("");
  const [receiverValidation, setReceiverValidation] = useState<ReceiverValidationResponse | null>(null);
  const [validationLoading, setValidationLoading] = useState(false);

  const [transferLoading, setTransferLoading] = useState(false);
  const [transferError, setTransferError] = useState("");
  const [transferResult, setTransferResult] = useState<TransferInitiateResponse | null>(null);
  const [pendingMfaTransferId, setPendingMfaTransferId] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaChallenge, setMfaChallenge] = useState<TransferMfaChallengeResponse | null>(null);
  const [mfaChallengeLoading, setMfaChallengeLoading] = useState(false);
  const [mfaVerifyLoading, setMfaVerifyLoading] = useState(false);
  const [mfaError, setMfaError] = useState("");
  const [adminApiKey, setAdminApiKey] = useState("");
  const [adminUnblockEmail, setAdminUnblockEmail] = useState("");
  const [adminUnblockUserId, setAdminUnblockUserId] = useState("");
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminError, setAdminError] = useState("");
  const [adminResult, setAdminResult] = useState<AdminUnblockUserResponse | null>(null);

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

  useEffect(() => {
    if (!session?.access_token) {
      setDashboard(null);
      setHistory([]);
      return;
    }
    void loadDashboardAndHistory(session.access_token);
  }, [session?.access_token]);

  async function loadDashboardAndHistory(accessToken: string) {
    setDashboardLoading(true);
    setDashboardError("");
    try {
      const [dashboardResponse, historyResponse] = await Promise.all([
        fetchDashboard(accessToken),
        fetchTransactionHistory(accessToken, 50, 0),
      ]);
      setDashboard(dashboardResponse);
      setHistory(historyResponse.items);
    } catch (error) {
      setDashboardError(error instanceof Error ? error.message : "Failed to load dashboard.");
    } finally {
      setDashboardLoading(false);
    }
  }

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
    setReceiverValidation(null);
    setTransferResult(null);
    setTransferError("");
    setDashboardError("");
    setSeedMessage("");
    setPendingMfaTransferId("");
    setMfaCode("");
    setMfaChallenge(null);
    setMfaError("");
    setAdminError("");
    setAdminResult(null);
  }

  function clearTransferWorkflowState() {
    setReceiverValidation(null);
    setTransferResult(null);
    setTransferError("");
    setPendingMfaTransferId("");
    setMfaCode("");
    setMfaChallenge(null);
    setMfaError("");
  }

  async function handleValidateReceiver() {
    if (!session?.access_token) {
      return;
    }
    setValidationLoading(true);
    setTransferError("");
    try {
      const response = await validateReceiver(session.access_token, {
        receiver_account_number: receiverAccountNumber.trim(),
        receiver_bank_code: receiverBankCode.trim(),
      });
      setReceiverValidation(response);
    } catch (error) {
      setReceiverValidation(null);
      setTransferError(error instanceof Error ? error.message : "Receiver validation failed.");
    } finally {
      setValidationLoading(false);
    }
  }

  async function handleInitiateTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session?.access_token) {
      setTransferError("No active user session. Please sign in again.");
      return;
    }

    const transferAmount = Number(amount);
    if (!Number.isFinite(transferAmount) || transferAmount <= 0) {
      setTransferError("Amount must be greater than zero.");
      return;
    }

    if (!receiverValidation?.exists) {
      setTransferError("Validate receiver account before initiating transfer.");
      return;
    }

    setTransferLoading(true);
    setTransferError("");
    setTransferResult(null);

    const payload: InitiateTransferRequest = {
      receiver_account_number: receiverAccountNumber.trim(),
      receiver_bank_code: receiverBankCode.trim(),
      amount: transferAmount,
      note: note.trim() || undefined,
    };

    try {
      const response = await initiateTransfer(session.access_token, payload);
      setTransferResult(response);
      setMfaError("");

      if (response.force_logout) {
        setAuthError(response.message);
        await handleSignOut();
        return;
      }

      if (response.mfa_required) {
        setPendingMfaTransferId(response.transfer_id);
        await handleRequestMfaChallenge(response.transfer_id, true);
      } else {
        setPendingMfaTransferId("");
        setMfaChallenge(null);
      }

      await loadDashboardAndHistory(session.access_token);
    } catch (error) {
      setTransferError(error instanceof Error ? error.message : "Transfer initiation failed.");
    } finally {
      setTransferLoading(false);
    }
  }

  async function handleRequestMfaChallenge(transferId?: string, silent = false) {
    if (!session?.access_token) {
      return;
    }

    const resolvedTransferId = (transferId || pendingMfaTransferId).trim();
    if (!resolvedTransferId) {
      setMfaError("No MFA transfer ID available.");
      return;
    }

    setMfaChallengeLoading(true);
    if (!silent) {
      setMfaError("");
    }
    try {
      const challenge = await requestTransferMfaChallenge(session.access_token, resolvedTransferId);
      setPendingMfaTransferId(challenge.transfer_id);
      setMfaChallenge(challenge);
      setTransferError("");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to request MFA challenge.";
      setMfaError(message);
      if (!silent) {
        setTransferError(message);
      }
    } finally {
      setMfaChallengeLoading(false);
    }
  }

  async function handleVerifyMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session?.access_token) {
      setMfaError("No active user session. Please sign in again.");
      return;
    }
    if (!pendingMfaTransferId.trim()) {
      setMfaError("No pending MFA transfer found.");
      return;
    }
    if (!mfaCode.trim()) {
      setMfaError("Enter the MFA code.");
      return;
    }

    setMfaVerifyLoading(true);
    setMfaError("");
    try {
      const response = await verifyTransferMfa(session.access_token, pendingMfaTransferId.trim(), {
        code: mfaCode.trim(),
      });
      setTransferResult(response);
      setPendingMfaTransferId("");
      setMfaCode("");
      setMfaChallenge(null);
      await loadDashboardAndHistory(session.access_token);
    } catch (error) {
      setMfaError(error instanceof Error ? error.message : "MFA verification failed.");
    } finally {
      setMfaVerifyLoading(false);
    }
  }

  async function handleSeedDemoData() {
    if (!session?.access_token) {
      return;
    }

    setSeedLoading(true);
    setDashboardError("");
    setTransferError("");
    setTransferResult(null);
    try {
      const response = await seedDemoBankingData(session.access_token);
      setSeedMessage(
        `${response.message} Seeded ${response.transfers_seeded} transfers and ${response.completed_transfers} completed postings.`,
      );
      await loadDashboardAndHistory(session.access_token);
    } catch (error) {
      setSeedMessage("");
      setDashboardError(error instanceof Error ? error.message : "Failed to seed demo data.");
    } finally {
      setSeedLoading(false);
    }
  }

  async function handleAdminUnblock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const key = adminApiKey.trim();
    const email = adminUnblockEmail.trim();
    const userId = adminUnblockUserId.trim();

    if (!key) {
      setAdminError("Enter admin API key.");
      return;
    }
    if (!email && !userId) {
      setAdminError("Enter email or user ID.");
      return;
    }

    setAdminLoading(true);
    setAdminError("");
    setAdminResult(null);
    try {
      const payload = {
        ...(email ? { email } : {}),
        ...(userId ? { user_id: userId } : {}),
      };
      const response = await adminUnblockUser(key, payload);
      setAdminResult(response);
      if (session?.access_token) {
        await loadDashboardAndHistory(session.access_token);
      }
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Failed to unblock user.");
    } finally {
      setAdminLoading(false);
    }
  }

  if (supabaseConfigError) {
    return (
      <main className="layout">
        <section className="panel error-panel">
          <h1>E-Banking Console</h1>
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
        <h1>E-Banking Dashboard</h1>
        <p>Sender-side transfer console with integrated fraud decisioning and account lifecycle controls.</p>
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

          {dashboardError && <section className="panel"><p className="error">{dashboardError}</p></section>}

          {dashboardLoading && !dashboard ? (
            <section className="panel">
              <p className="muted">Loading account details...</p>
            </section>
          ) : dashboard ? (
            <>
              <section className="panel account-panel">
                <div className="panel-header">
                  <div>
                    <h2>Account Summary</h2>
                    <p>Available sender account used for transfer initiation.</p>
                  </div>
                  <button className="secondary-btn" onClick={handleSeedDemoData} disabled={seedLoading}>
                    {seedLoading ? "Seeding Demo Data..." : "Load Demo Data"}
                  </button>
                </div>
                <div className="account-grid">
                  <div>
                    <span className="muted">Account Number</span>
                    <strong>{dashboard.account.account_number}</strong>
                  </div>
                  <div>
                    <span className="muted">Bank Code</span>
                    <strong>{dashboard.account.bank_code}</strong>
                  </div>
                  <div>
                    <span className="muted">Balance</span>
                    <strong>{formatCurrency(dashboard.account.balance, dashboard.account.currency)}</strong>
                  </div>
                  <div>
                    <span className="muted">Status</span>
                    <strong>{dashboard.account.is_active ? "ACTIVE" : "BLOCKED"}</strong>
                  </div>
                </div>
                {seedMessage && <p className="muted">{seedMessage}</p>}
              </section>

              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>Admin Controls</h2>
                    <p>Reactivate blocked account/users using admin API key (local ops tool).</p>
                  </div>
                </div>
                <form onSubmit={handleAdminUnblock}>
                  <div className="grid">
                    <label className="field">
                      <span>Admin API Key</span>
                      <input
                        type="password"
                        value={adminApiKey}
                        onChange={(event) => setAdminApiKey(event.target.value)}
                        placeholder="X-Admin-Key"
                        required
                        disabled={adminLoading}
                      />
                    </label>
                    <label className="field">
                      <span>User Email</span>
                      <input
                        type="email"
                        value={adminUnblockEmail}
                        onChange={(event) => setAdminUnblockEmail(event.target.value)}
                        placeholder="user@example.com"
                        disabled={adminLoading}
                      />
                    </label>
                    <label className="field">
                      <span>User ID (optional)</span>
                      <input
                        type="text"
                        value={adminUnblockUserId}
                        onChange={(event) => setAdminUnblockUserId(event.target.value)}
                        placeholder="uuid or user id"
                        disabled={adminLoading}
                      />
                    </label>
                  </div>
                  <div className="transfer-actions">
                    <button type="submit" className="primary-btn" disabled={adminLoading}>
                      {adminLoading ? "Unblocking..." : "Unblock User"}
                    </button>
                  </div>
                </form>
                {adminError && <p className="error">{adminError}</p>}
                {adminResult && (
                  <div className="transfer-result">
                    <p>{adminResult.message}</p>
                    <p className="muted">
                      {adminResult.email || adminResult.user_id} | Status: {adminResult.user_status} | Account Active:{" "}
                      {String(adminResult.account_active)}
                    </p>
                    <p className="muted">
                      {adminResult.bank_code}/{adminResult.account_number}
                    </p>
                  </div>
                )}
              </section>

              <div className="content-grid banking-grid">
                <section className="panel">
                  <div className="panel-header">
                    <h2>Send Money</h2>
                    <p>Receiver validation + transfer initiation. Fraud features are auto-computed by backend.</p>
                  </div>

                  <form onSubmit={handleInitiateTransfer}>
                    <div className="grid">
                      <label className="field">
                        <span>Receiver Bank Code</span>
                        <input
                          type="text"
                          value={receiverBankCode}
                          onChange={(event) => {
                            setReceiverBankCode(event.target.value);
                            clearTransferWorkflowState();
                          }}
                          required
                          disabled={transferLoading || validationLoading}
                        />
                      </label>
                      <label className="field">
                        <span>Receiver Account Number</span>
                        <input
                          type="text"
                          value={receiverAccountNumber}
                          onChange={(event) => {
                            setReceiverAccountNumber(event.target.value);
                            clearTransferWorkflowState();
                          }}
                          required
                          disabled={transferLoading || validationLoading}
                        />
                      </label>
                      <label className="field">
                        <span>Amount</span>
                        <input
                          type="number"
                          min={0.01}
                          step="0.01"
                          value={amount}
                          onChange={(event) => setAmount(event.target.value)}
                          required
                          disabled={transferLoading || validationLoading}
                        />
                      </label>
                      <label className="field">
                        <span>Note</span>
                        <input
                          type="text"
                          value={note}
                          onChange={(event) => setNote(event.target.value)}
                          maxLength={200}
                          disabled={transferLoading || validationLoading}
                        />
                      </label>
                    </div>

                    <div className="transfer-actions">
                      <button
                        type="button"
                        className="secondary-btn"
                        onClick={handleValidateReceiver}
                        disabled={validationLoading || transferLoading || !receiverAccountNumber.trim()}
                      >
                        {validationLoading ? "Validating..." : "Validate Receiver"}
                      </button>
                      <button
                        type="submit"
                        className="primary-btn"
                        disabled={transferLoading || !receiverValidation?.exists}
                      >
                        {transferLoading ? "Processing..." : "Initiate Transfer"}
                      </button>
                    </div>
                  </form>

                  {receiverValidation && (
                    <div className={`validation-box ${receiverValidation.exists ? "valid" : "invalid"}`}>
                      <strong>{receiverValidation.exists ? "Receiver Validated" : "Receiver Not Found"}</strong>
                      <p>{receiverValidation.message}</p>
                      {receiverValidation.exists && (
                        <p>
                          {receiverValidation.account_holder || "Unknown Holder"} -{" "}
                          {receiverValidation.account_number_masked} ({receiverValidation.bank_code})
                        </p>
                      )}
                    </div>
                  )}

                  {transferError && <p className="error">{transferError}</p>}
                  {transferResult && (
                    <div className="transfer-result">
                      <div className={riskClassName(transferResult.risk_level)}>
                        <span>{transferResult.risk_level || "N/A"}</span>
                        <strong>{transferResult.action || transferResult.status}</strong>
                      </div>
                      <p>{transferResult.message}</p>
                      <p className="muted">Transfer ID: {transferResult.transfer_id}</p>
                      {transferResult.fraud_probability !== null && (
                        <p className="muted">
                          Fraud Probability: {(transferResult.fraud_probability * 100).toFixed(2)}%
                        </p>
                      )}
                    </div>
                  )}

                  {pendingMfaTransferId && (
                    <div className="transfer-result">
                      <h3>MFA Verification Required</h3>
                      <p className="muted">Transfer ID: {pendingMfaTransferId}</p>
                      {mfaChallenge && (
                        <>
                          <p>{mfaChallenge.message}</p>
                          <p className="muted">
                            Expires At: {formatDateTime(mfaChallenge.expires_at)} | Attempts Left:{" "}
                            {mfaChallenge.remaining_attempts}
                          </p>
                          {mfaChallenge.demo_code && (
                            <p className="muted">
                              Demo Code (local only): <strong>{mfaChallenge.demo_code}</strong>
                            </p>
                          )}
                        </>
                      )}
                      <form onSubmit={handleVerifyMfa}>
                        <div className="grid">
                          <label className="field">
                            <span>MFA Code</span>
                            <input
                              type="text"
                              inputMode="numeric"
                              value={mfaCode}
                              onChange={(event) => setMfaCode(event.target.value)}
                              placeholder="Enter OTP/security code"
                              disabled={mfaVerifyLoading}
                              required
                            />
                          </label>
                        </div>
                        <div className="transfer-actions">
                          <button
                            type="button"
                            className="secondary-btn"
                            onClick={() => void handleRequestMfaChallenge()}
                            disabled={mfaChallengeLoading || mfaVerifyLoading}
                          >
                            {mfaChallengeLoading ? "Requesting..." : "Resend Code"}
                          </button>
                          <button type="submit" className="primary-btn" disabled={mfaVerifyLoading}>
                            {mfaVerifyLoading ? "Verifying..." : "Verify & Complete Transfer"}
                          </button>
                        </div>
                      </form>
                      {mfaError && <p className="error">{mfaError}</p>}
                    </div>
                  )}
                </section>

                <section className="panel">
                  <div className="panel-header">
                    <h2>Historical Transactions</h2>
                    <p>Most recent incoming/outgoing transfers from your account.</p>
                  </div>

                  {history.length === 0 ? (
                    <p className="muted">No transaction history yet.</p>
                  ) : (
                    <div className="history-table-wrap">
                      <table className="history-table">
                        <thead>
                          <tr>
                            <th>Time</th>
                            <th>Direction</th>
                            <th>Counterparty</th>
                            <th>Amount</th>
                            <th>Status</th>
                            <th>Risk</th>
                          </tr>
                        </thead>
                        <tbody>
                          {history.map((item) => (
                            <tr key={item.transfer_id}>
                              <td>{formatDateTime(item.created_at)}</td>
                              <td>{item.direction}</td>
                              <td>
                                {item.counterparty_bank_code}/{item.counterparty_account_number}
                              </td>
                              <td>{formatCurrency(item.amount, dashboard.account.currency)}</td>
                              <td>{item.status}</td>
                              <td>
                                <span className={riskClassName(item.risk_level)}>{item.risk_level || "N/A"}</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </div>
            </>
          ) : null}
        </section>
      )}
    </main>
  );
}
