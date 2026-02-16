import { useCallback, useEffect, useMemo, useState } from "react";
import {
  adminUnblockUser,
  fetchAdminAccounts,
  fetchAdminTransfers,
  fetchAdminUsers,
  updateAdminAccountBalance,
} from "../../services/adminApi";
import type { AdminAccountRow, AdminTransferRow, AdminUserRow } from "../../types";
import { formatCurrency, formatDateTime, riskBadgeClass } from "../../services/formatters";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { Table } from "../../components/ui/Table";
import { useToast } from "../../components/ui/Toast";
import { BuildingIcon, HistoryIcon, LogoutIcon, ShieldIcon, UserIcon } from "../../components/icons";

type Props = {
  adminApiKey: string;
  onLogout: () => void;
};

type AdminTab = "users" | "accounts" | "transfers";

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

export function AdminPanel({ adminApiKey, onLogout }: Props) {
  const { pushToast } = useToast();

  const [activeTab, setActiveTab] = useState<AdminTab>("users");
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [accounts, setAccounts] = useState<AdminAccountRow[]>([]);
  const [transfers, setTransfers] = useState<AdminTransferRow[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [balanceDrafts, setBalanceDrafts] = useState<Record<string, string>>({});

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setErrorMessage("");
    try {
      const response = await fetchAdminUsers(adminApiKey, 100, 0);
      setUsers(response.items);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch users.";
      setErrorMessage(message);
      pushToast(message, "error");
    } finally {
      setLoading(false);
    }
  }, [adminApiKey, pushToast]);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    setErrorMessage("");
    try {
      const response = await fetchAdminAccounts(adminApiKey, 100, 0);
      setAccounts(response.items);
      setBalanceDrafts(
        response.items.reduce<Record<string, string>>((acc, account) => {
          acc[account.account_id] = String(account.balance);
          return acc;
        }, {}),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch accounts.";
      setErrorMessage(message);
      pushToast(message, "error");
    } finally {
      setLoading(false);
    }
  }, [adminApiKey, pushToast]);

  const loadTransfers = useCallback(async () => {
    setLoading(true);
    setErrorMessage("");
    try {
      const response = await fetchAdminTransfers(adminApiKey, 100, 0);
      setTransfers(response.items);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch transfer requests.";
      setErrorMessage(message);
      pushToast(message, "error");
    } finally {
      setLoading(false);
    }
  }, [adminApiKey, pushToast]);

  useEffect(() => {
    if (activeTab === "users") {
      void loadUsers();
    }
    if (activeTab === "accounts") {
      void loadAccounts();
    }
    if (activeTab === "transfers") {
      void loadTransfers();
    }
  }, [activeTab, loadAccounts, loadTransfers, loadUsers]);

  async function handleUnblockUser(row: AdminUserRow) {
    try {
      await adminUnblockUser(adminApiKey, {
        user_id: row.user_id,
        email: row.email,
      });
      pushToast(`User ${row.email} unblocked.`, "success");
      await loadUsers();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to unblock user.";
      pushToast(message, "error");
    }
  }

  async function handleBalanceSave(account: AdminAccountRow) {
    const draft = balanceDrafts[account.account_id];
    const parsed = Number(draft);
    if (!Number.isFinite(parsed) || parsed < 0) {
      pushToast("Balance must be a valid non-negative number.", "error");
      return;
    }

    try {
      const response = await updateAdminAccountBalance(adminApiKey, account.account_id, {
        balance: parsed,
      });
      setAccounts((prev) =>
        prev.map((item) => (item.account_id === account.account_id ? { ...item, balance: response.balance } : item)),
      );
      setBalanceDrafts((prev) => ({ ...prev, [account.account_id]: String(response.balance) }));
      pushToast(response.message || "Balance updated.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to update account balance.";
      pushToast(message, "error");
    }
  }

  const userColumns = useMemo(
    () => [
      {
        key: "id",
        title: "User ID",
        render: (row: AdminUserRow) => row.user_id,
      },
      {
        key: "name",
        title: "Name",
        render: (row: AdminUserRow) => row.name || "N/A",
      },
      {
        key: "email",
        title: "Email",
        render: (row: AdminUserRow) => row.email || "N/A",
      },
      {
        key: "status",
        title: "Status",
        render: (row: AdminUserRow) => (
          <span className={row.status === "BLOCKED" ? "status-badge status-badge-danger" : "status-badge status-badge-success"}>
            {row.status}
          </span>
        ),
      },
      {
        key: "action",
        title: "Action",
        render: (row: AdminUserRow) =>
          row.status === "BLOCKED" ? (
            <Button variant="secondary" size="sm" onClick={() => void handleUnblockUser(row)}>
              Unblock
            </Button>
          ) : (
            <span className="table-muted">No action</span>
          ),
      },
    ],
    [],
  );

  const accountColumns = useMemo(
    () => [
      {
        key: "number",
        title: "Account Number",
        render: (row: AdminAccountRow) => `${row.bank_code}/${row.account_number}`,
      },
      {
        key: "holder",
        title: "Account Holder",
        render: (row: AdminAccountRow) => row.account_holder_name,
      },
      {
        key: "balance",
        title: "Balance",
        render: (row: AdminAccountRow) => (
          <div className="balance-edit-cell">
            <Input
              label=""
              aria-label={`Balance for ${row.account_number}`}
              value={balanceDrafts[row.account_id] || ""}
              onChange={(event) =>
                setBalanceDrafts((prev) => ({
                  ...prev,
                  [row.account_id]: event.target.value,
                }))
              }
            />
            <Button variant="secondary" size="sm" onClick={() => void handleBalanceSave(row)}>
              Save
            </Button>
          </div>
        ),
      },
    ],
    [balanceDrafts],
  );

  const transferColumns = useMemo(
    () => [
      {
        key: "sender",
        title: "Sender",
        render: (row: AdminTransferRow) => row.sender,
      },
      {
        key: "receiver",
        title: "Receiver",
        render: (row: AdminTransferRow) => row.receiver,
      },
      {
        key: "amount",
        title: "Amount",
        render: (row: AdminTransferRow) => formatCurrency(row.amount, "USD"),
      },
      {
        key: "risk",
        title: "Risk Score",
        render: (row: AdminTransferRow) => (
          <span className={riskBadgeClass(row.risk_score !== null ? (row.risk_score > 0.5 ? "HIGH" : row.risk_score > 0.1 ? "MEDIUM" : "LOW") : null)}>
            {row.risk_score === null ? "N/A" : row.risk_score.toFixed(2)}
          </span>
        ),
      },
      {
        key: "status",
        title: "Status",
        render: (row: AdminTransferRow) => <span className={statusBadgeClass(row.status)}>{row.status}</span>,
      },
      {
        key: "time",
        title: "Timestamp",
        render: (row: AdminTransferRow) => formatDateTime(row.timestamp),
      },
    ],
    [],
  );

  return (
    <main className="app-shell admin-shell">
      <header className="top-header">
        <div>
          <h1>IntelliBank Admin Panel</h1>
          <p>Operational controls for users, accounts, and transfer review.</p>
        </div>
        <Button variant="ghost" onClick={onLogout}>
          <LogoutIcon width={16} height={16} />
          Exit Admin
        </Button>
      </header>

      <div className="admin-layout">
        <aside className="admin-sidebar">
          <button
            type="button"
            className={activeTab === "users" ? "active" : ""}
            onClick={() => setActiveTab("users")}
          >
            <UserIcon width={16} height={16} />
            Bank Users
          </button>
          <button
            type="button"
            className={activeTab === "accounts" ? "active" : ""}
            onClick={() => setActiveTab("accounts")}
          >
            <BuildingIcon width={16} height={16} />
            Bank Accounts
          </button>
          <button
            type="button"
            className={activeTab === "transfers" ? "active" : ""}
            onClick={() => setActiveTab("transfers")}
          >
            <HistoryIcon width={16} height={16} />
            Transfer Requests
          </button>
          <div className="admin-sidebar-note">
            <ShieldIcon width={16} height={16} />
            <p>Admin endpoints must be enabled in backend for all panels.</p>
          </div>
        </aside>

        <section className="admin-content">
          {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
          {loading ? (
            <div className="table-loading">
              <Spinner />
            </div>
          ) : null}

          {activeTab === "users" ? (
            <Card title="Bank Users" subtitle="Block status and unblock controls.">
              <Table columns={userColumns} rows={users} rowKey={(row) => row.user_id} emptyMessage="No user records found." />
            </Card>
          ) : null}

          {activeTab === "accounts" ? (
            <Card title="Bank Accounts" subtitle="Adjust account balances and save changes.">
              <Table
                columns={accountColumns}
                rows={accounts}
                rowKey={(row) => row.account_id}
                emptyMessage="No account records found."
              />
            </Card>
          ) : null}

          {activeTab === "transfers" ? (
            <Card title="Transfer Requests" subtitle="Read-only risk and status timeline.">
              <Table
                columns={transferColumns}
                rows={transfers}
                rowKey={(row) => row.transfer_id}
                emptyMessage="No transfer requests found."
              />
            </Card>
          ) : null}
        </section>
      </div>
    </main>
  );
}
