import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  fetchDashboard,
  fetchTransactionHistory,
  initiateTransfer,
  requestTransferMfaChallenge,
  seedDemoBankingData,
  validateReceiver,
  verifyTransferMfa,
} from "../../services/bankingApi";
import type {
  DashboardResponse,
  ReceiverValidationResponse,
  TransferHistoryItem,
  TransferMfaChallengeResponse,
} from "../../types";
import { extractFirstName, formatCurrency, formatDateTime, getGreeting, riskBadgeClass } from "../../services/formatters";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { Table } from "../../components/ui/Table";
import { useToast } from "../../components/ui/Toast";
import { HistoryIcon, LogoutIcon, SendIcon, ShieldIcon, UserIcon } from "../../components/icons";

type Props = {
  accessToken: string;
  email: string;
  onLogout: () => Promise<void>;
};

type SuccessPayload = {
  receiverName: string;
  bankName: string;
  amount: number;
  message: string;
};

type ActionCardProps = {
  title: string;
  description: string;
  imageSrc: string;
  fallbackIcon: ReactNode;
  onClick: () => void;
};

function ActionCard({ title, description, imageSrc, fallbackIcon, onClick }: ActionCardProps) {
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <button type="button" className="action-card" onClick={onClick}>
      <div className="action-card-icon-wrap">
        {imageFailed ? (
          <span className="action-card-icon">{fallbackIcon}</span>
        ) : (
          <img src={imageSrc} alt={title} className="action-card-image" onError={() => setImageFailed(true)} />
        )}
      </div>
      <div className="action-card-content">
        <h4>{title}</h4>
        <p>{description}</p>
      </div>
    </button>
  );
}

function statusBadgeClass(status: string): string {
  if (status.includes("BLOCK") || status.includes("REJECTED")) {
    return "status-badge status-badge-danger";
  }
  if (status.includes("MFA")) {
    return "status-badge status-badge-warning";
  }
  if (status.includes("COMPLETE")) {
    return "status-badge status-badge-success";
  }
  return "status-badge status-badge-neutral";
}

export function UserDashboard({ accessToken, email, onLogout }: Props) {
  const { pushToast } = useToast();

  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [transactions, setTransactions] = useState<TransferHistoryItem[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [transactionsLoading, setTransactionsLoading] = useState(true);
  const [pageOffset, setPageOffset] = useState(0);
  const pageLimit = 8;

  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [sendModalOpen, setSendModalOpen] = useState(false);
  const [otpModalOpen, setOtpModalOpen] = useState(false);
  const [successModalPayload, setSuccessModalPayload] = useState<SuccessPayload | null>(null);

  const [receiverBankCode, setReceiverBankCode] = useState("CAPBANK001");
  const [receiverAccountNumber, setReceiverAccountNumber] = useState("");
  const [amount, setAmount] = useState("");
  const [remarks, setRemarks] = useState("");
  const [validation, setValidation] = useState<ReceiverValidationResponse | null>(null);
  const [validationLoading, setValidationLoading] = useState(false);
  const [transferLoading, setTransferLoading] = useState(false);

  const [pendingTransferId, setPendingTransferId] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaChallenge, setMfaChallenge] = useState<TransferMfaChallengeResponse | null>(null);
  const [mfaLoading, setMfaLoading] = useState(false);
  const [mfaError, setMfaError] = useState("");

  const firstName = useMemo(() => extractFirstName(email), [email]);
  const greeting = useMemo(() => getGreeting(), []);

  const loadDashboard = useCallback(async () => {
    setDashboardLoading(true);
    try {
      const response = await fetchDashboard(accessToken);
      setDashboard(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load dashboard.";
      pushToast(message, "error");
    } finally {
      setDashboardLoading(false);
    }
  }, [accessToken, pushToast]);

  const loadTransactions = useCallback(async () => {
    setTransactionsLoading(true);
    try {
      const response = await fetchTransactionHistory(accessToken, pageLimit, pageOffset);
      setTransactions(response.items);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load transaction history.";
      pushToast(message, "error");
      setTransactions([]);
    } finally {
      setTransactionsLoading(false);
    }
  }, [accessToken, pageOffset, pushToast]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    void loadTransactions();
  }, [loadTransactions]);

  function resetTransferForm() {
    setReceiverBankCode("CAPBANK001");
    setReceiverAccountNumber("");
    setAmount("");
    setRemarks("");
    setValidation(null);
    setTransferLoading(false);
  }

  async function handleSeedDemoData() {
    try {
      const response = await seedDemoBankingData(accessToken);
      pushToast(response.message, "success");
      setPageOffset(0);
      await Promise.all([loadDashboard(), loadTransactions()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load demo data.";
      pushToast(message, "error");
    }
  }

  async function handleValidateReceiver() {
    if (!receiverAccountNumber.trim()) {
      pushToast("Receiver account number is required.", "error");
      return;
    }

    setValidationLoading(true);
    try {
      const response = await validateReceiver(accessToken, {
        receiver_account_number: receiverAccountNumber.trim(),
        receiver_bank_code: receiverBankCode.trim(),
      });
      setValidation(response);
      pushToast(response.message, response.exists ? "success" : "error");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Receiver validation failed.";
      pushToast(message, "error");
      setValidation(null);
    } finally {
      setValidationLoading(false);
    }
  }

  async function requestMfaChallenge(transferId: string) {
    setMfaLoading(true);
    setMfaError("");
    try {
      const challenge = await requestTransferMfaChallenge(accessToken, transferId);
      setPendingTransferId(challenge.transfer_id);
      setMfaChallenge(challenge);
      pushToast("OTP challenge generated.", "info");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to generate OTP challenge.";
      setMfaError(message);
      pushToast(message, "error");
    } finally {
      setMfaLoading(false);
    }
  }

  async function handleTransferSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!validation?.exists) {
      pushToast("Validate the receiver before sending money.", "error");
      return;
    }

    const parsedAmount = Number(amount);
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      pushToast("Amount must be greater than zero.", "error");
      return;
    }

    setTransferLoading(true);
    try {
      const response = await initiateTransfer(accessToken, {
        receiver_account_number: receiverAccountNumber.trim(),
        receiver_bank_code: receiverBankCode.trim(),
        amount: parsedAmount,
        note: remarks.trim() || undefined,
      });

      if (response.force_logout) {
        pushToast("Suspicious activity detected. Logging out.", "error");
        window.alert("Suspicious activity detected.");
        await onLogout();
        return;
      }

      if (response.mfa_required) {
        setPendingTransferId(response.transfer_id);
        setOtpModalOpen(true);
        await requestMfaChallenge(response.transfer_id);
      } else {
        setSuccessModalPayload({
          receiverName: validation.account_holder || validation.account_number_masked || "Receiver",
          bankName: validation.bank_code || receiverBankCode,
          amount: parsedAmount,
          message: "Transaction Successful",
        });
        setSendModalOpen(false);
        resetTransferForm();
      }

      await Promise.all([loadDashboard(), loadTransactions()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Transfer initiation failed.";
      pushToast(message, "error");
    } finally {
      setTransferLoading(false);
    }
  }

  async function handleVerifyOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!pendingTransferId.trim()) {
      setMfaError("Transfer reference is missing.");
      return;
    }

    if (!mfaCode.trim()) {
      setMfaError("Enter OTP code.");
      return;
    }

    setMfaLoading(true);
    setMfaError("");
    try {
      const response = await verifyTransferMfa(accessToken, pendingTransferId, {
        code: mfaCode.trim(),
      });

      if (response.force_logout) {
        pushToast("Suspicious activity detected. Logging out.", "error");
        window.alert("Suspicious activity detected.");
        await onLogout();
        return;
      }

      setOtpModalOpen(false);
      setPendingTransferId("");
      setMfaCode("");
      setMfaChallenge(null);

      setSuccessModalPayload({
        receiverName: validation?.account_holder || validation?.account_number_masked || "Receiver",
        bankName: validation?.bank_code || receiverBankCode,
        amount: Number(amount) || 0,
        message: response.message || "Transaction Successful",
      });
      setSendModalOpen(false);
      resetTransferForm();
      pushToast("OTP verified and transaction completed.", "success");
      await Promise.all([loadDashboard(), loadTransactions()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Invalid OTP.";
      setMfaError(message);
      pushToast(message, "error");
    } finally {
      setMfaLoading(false);
    }
  }

  const transactionColumns = useMemo(
    () => [
      {
        key: "date",
        title: "Date",
        render: (row: TransferHistoryItem) => formatDateTime(row.created_at),
      },
      {
        key: "counterparty",
        title: "To / From",
        render: (row: TransferHistoryItem) =>
          `${row.direction === "OUTGOING" ? "To" : "From"} ${row.counterparty_bank_code}/${row.counterparty_account_number}`,
      },
      {
        key: "amount",
        title: "Amount",
        render: (row: TransferHistoryItem) =>
          formatCurrency(row.amount, dashboard?.account.currency || "USD"),
      },
      {
        key: "status",
        title: "Status",
        render: (row: TransferHistoryItem) => <span className={statusBadgeClass(row.status)}>{row.status}</span>,
      },
      {
        key: "risk",
        title: "Risk",
        render: (row: TransferHistoryItem) => (
          <span className={riskBadgeClass(row.risk_level)}>{row.risk_level || "N/A"}</span>
        ),
      },
    ],
    [dashboard?.account.currency],
  );

  return (
    <main className="app-shell">
      <header className="top-header">
        <div>
          <h1>{greeting}</h1>
          <p>Welcome Back, {firstName}</p>
        </div>
        <div className="profile-menu-wrap">
          <button type="button" className="profile-button" onClick={() => setShowProfileMenu((prev) => !prev)}>
            <UserIcon width={18} height={18} />
            <span>Profile</span>
          </button>
          {showProfileMenu ? (
            <div className="profile-menu" role="menu">
              <button type="button" onClick={() => void onLogout()}>
                <LogoutIcon width={16} height={16} />
                Logout
              </button>
            </div>
          ) : null}
        </div>
      </header>

      <section className="dashboard-grid">
        <Card className="balance-card">
          {dashboardLoading ? (
            <Spinner />
          ) : dashboard ? (
            <>
              <p className="balance-label">Available Balance</p>
              <p className="balance-value">{formatCurrency(dashboard.account.balance, dashboard.account.currency)}</p>
              <p className="balance-meta">
                Account {dashboard.account.account_number} | {dashboard.account.bank_code}
              </p>
            </>
          ) : (
            <p>Unable to load balance.</p>
          )}
        </Card>

        <div className="action-grid">
          <ActionCard
            title="Send Money"
            description="Transfer funds with real-time AI risk checks."
            imageSrc="/send_icon.png"
            fallbackIcon={<SendIcon width={22} height={22} />}
            onClick={() => setSendModalOpen(true)}
          />
          <ActionCard
            title="Transaction History"
            description="Review outgoing and incoming payments."
            imageSrc="/history_icon.png"
            fallbackIcon={<HistoryIcon width={22} height={22} />}
            onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })}
          />
          <ActionCard
            title="Security Status"
            description="Monitor risk posture and verification events."
            imageSrc="/security_icon.png"
            fallbackIcon={<ShieldIcon width={22} height={22} />}
            onClick={() => pushToast("Security telemetry healthy.", "info")}
          />
        </div>
      </section>

      <Card
        title="Historical Transactions"
        subtitle="Date, counterparty, amount, and risk decisions."
        actions={
          <div className="table-pagination">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPageOffset((prev) => Math.max(prev - pageLimit, 0))}
              disabled={pageOffset === 0 || transactionsLoading}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPageOffset((prev) => prev + pageLimit)}
              disabled={transactions.length < pageLimit || transactionsLoading}
            >
              Next
            </Button>
          </div>
        }
      >
        {transactionsLoading ? (
          <div className="table-loading">
            <Spinner />
          </div>
        ) : (
          <Table
            columns={transactionColumns}
            rows={transactions}
            rowKey={(row) => row.transfer_id}
            emptyMessage="No transactions found."
          />
        )}
      </Card>

      <section className="dashboard-footer-actions">
        <Button variant="secondary" onClick={handleSeedDemoData}>
          Load Demo Data
        </Button>
      </section>

      <Modal
        open={sendModalOpen}
        title="Send Money"
        onClose={() => {
          setSendModalOpen(false);
          resetTransferForm();
        }}
        size="lg"
      >
        <form className="send-form" onSubmit={handleTransferSubmit}>
          <div className="send-form-grid">
            <Input
              label="Account Number"
              value={receiverAccountNumber}
              onChange={(event) => {
                setReceiverAccountNumber(event.target.value);
                setValidation(null);
              }}
              placeholder="Receiver account number"
              required
            />
            <Input
              label="Bank Code"
              value={receiverBankCode}
              onChange={(event) => {
                setReceiverBankCode(event.target.value);
                setValidation(null);
              }}
              placeholder="CAPBANK001"
              required
            />
            <Input
              label="Amount"
              type="number"
              min={0.01}
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder="0.00"
              required
            />
            <Input
              label="Remarks"
              value={remarks}
              onChange={(event) => setRemarks(event.target.value)}
              placeholder="Optional note"
              maxLength={200}
            />
          </div>

          {validation ? (
            <div className={`receiver-validation ${validation.exists ? "valid" : "invalid"}`}>
              <strong>{validation.exists ? "Receiver validated" : "Receiver not found"}</strong>
              <p>{validation.message}</p>
            </div>
          ) : null}

          <div className="modal-button-row">
            <Button type="button" variant="secondary" loading={validationLoading} onClick={() => void handleValidateReceiver()}>
              Validate Receiver
            </Button>
            <Button type="submit" loading={transferLoading} disabled={!validation?.exists}>
              Validate & Send
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={otpModalOpen}
        title="MFA Verification"
        onClose={() => {
          setOtpModalOpen(false);
          setPendingTransferId("");
          setMfaCode("");
          setMfaChallenge(null);
          setMfaError("");
        }}
      >
        <form className="otp-form" onSubmit={handleVerifyOtp}>
          <p>Additional verification required for this transaction.</p>
          {mfaChallenge ? (
            <>
              <p className="ui-field-hint">
                Expires: {formatDateTime(mfaChallenge.expires_at)} | Attempts left: {mfaChallenge.remaining_attempts}
              </p>
              {mfaChallenge.demo_code ? (
                <div className="otp-demo-code">
                  <span>OTP Code</span>
                  <strong>{mfaChallenge.demo_code}</strong>
                </div>
              ) : (
                <p className="ui-field-hint">
                  OTP code delivery is external. Ask backend admin to enable demo OTP response if needed.
                </p>
              )}
            </>
          ) : null}
          <Input
            label="OTP"
            value={mfaCode}
            onChange={(event) => setMfaCode(event.target.value)}
            placeholder="Enter OTP"
            required
          />
          {mfaError ? <p className="form-error">{mfaError}</p> : null}
          <div className="modal-button-row">
            <Button type="button" variant="secondary" loading={mfaLoading} onClick={() => void requestMfaChallenge(pendingTransferId)}>
              Resend OTP
            </Button>
            <Button type="submit" loading={mfaLoading}>
              Verify
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(successModalPayload)}
        title="Transaction Successful"
        onClose={() => setSuccessModalPayload(null)}
      >
        {successModalPayload ? (
          <div className="success-modal-content">
            <p>{successModalPayload.message}</p>
            <div className="success-modal-grid">
              <div>
                <span>Receiver Account Name</span>
                <strong>{successModalPayload.receiverName}</strong>
              </div>
              <div>
                <span>Bank Name</span>
                <strong>{successModalPayload.bankName}</strong>
              </div>
              <div>
                <span>Amount</span>
                <strong>{formatCurrency(successModalPayload.amount, dashboard?.account.currency || "USD")}</strong>
              </div>
            </div>
            <div className="modal-button-row">
              <Button onClick={() => setSuccessModalPayload(null)}>Close</Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </main>
  );
}
