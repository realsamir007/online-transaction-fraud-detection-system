from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import UTC, datetime
import os
import random
from typing import Any

from supabase import Client

from app.database import DatabaseError


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class BankingConfig:
    default_bank_code: str = "CAPBANK001"
    default_currency: str = "USD"
    demo_initial_balance: float = 10000.0

    @classmethod
    def from_env(cls) -> "BankingConfig":
        raw_initial_balance = os.getenv("DEMO_INITIAL_BALANCE", "10000").strip()
        try:
            initial_balance = float(raw_initial_balance)
        except ValueError as exc:
            raise ValueError("DEMO_INITIAL_BALANCE must be numeric.") from exc
        if initial_balance < 0:
            raise ValueError("DEMO_INITIAL_BALANCE must be greater than or equal to 0.")

        bank_code = os.getenv("DEFAULT_BANK_CODE", "CAPBANK001").strip() or "CAPBANK001"
        currency = os.getenv("DEFAULT_CURRENCY", "USD").strip() or "USD"
        return cls(
            default_bank_code=bank_code,
            default_currency=currency,
            demo_initial_balance=initial_balance,
        )


class BankingRepository:
    def __init__(self, client: Client, config: BankingConfig) -> None:
        self.client = client
        self.config = config

    @staticmethod
    def _single_row(result: Any) -> dict[str, Any] | None:
        data = getattr(result, "data", None)
        if not data:
            return None
        if isinstance(data, list):
            return data[0] if data else None
        if isinstance(data, dict):
            return data
        return None

    @staticmethod
    def _rows(result: Any) -> list[dict[str, Any]]:
        data = getattr(result, "data", None)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []

    def _get_or_create_user_profile(self, user_id: str, email: str | None) -> dict[str, Any]:
        result = self.client.table("bank_users").select("*").eq("id", user_id).limit(1).execute()
        profile = self._single_row(result)
        if profile:
            return profile

        full_name = (email.split("@")[0] if email else f"user-{user_id[:8]}").replace(".", " ").title()
        payload = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "status": "ACTIVE",
            "created_at": _utcnow_iso(),
            "updated_at": _utcnow_iso(),
        }
        insert_result = self.client.table("bank_users").insert(payload).execute()
        created = self._single_row(insert_result)
        if not created:
            raise DatabaseError("Failed to create user banking profile.")
        return created

    @staticmethod
    def _generate_account_number() -> str:
        return f"{random.randint(0, 9999999999):010d}"

    def _create_account(self, user_id: str) -> dict[str, Any]:
        for _ in range(5):
            payload = {
                "user_id": user_id,
                "account_number": self._generate_account_number(),
                "bank_code": self.config.default_bank_code,
                "currency": self.config.default_currency,
                "balance": self.config.demo_initial_balance,
                "is_active": True,
                "created_at": _utcnow_iso(),
                "updated_at": _utcnow_iso(),
            }
            try:
                insert_result = self.client.table("bank_accounts").insert(payload).execute()
                account = self._single_row(insert_result)
                if account:
                    return account
            except Exception:
                continue
        raise DatabaseError("Unable to provision a bank account for user.")

    def get_or_create_user_account(self, user_id: str, email: str | None) -> dict[str, Any]:
        profile = self._get_or_create_user_profile(user_id=user_id, email=email)
        result = self.client.table("bank_accounts").select("*").eq("user_id", user_id).limit(1).execute()
        account = self._single_row(result)
        if not account:
            account = self._create_account(user_id=user_id)

        return {"profile": profile, "account": account}

    def get_account_by_bank_details(self, *, bank_code: str, account_number: str) -> dict[str, Any] | None:
        result = (
            self.client.table("bank_accounts")
            .select("*")
            .eq("bank_code", bank_code)
            .eq("account_number", account_number)
            .limit(1)
            .execute()
        )
        return self._single_row(result)

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        result = self.client.table("bank_users").select("*").eq("id", user_id).limit(1).execute()
        return self._single_row(result)

    def get_user_profile_by_email(self, email: str) -> dict[str, Any] | None:
        result = (
            self.client.table("bank_users")
            .select("*")
            .ilike("email", email)
            .limit(1)
            .execute()
        )
        return self._single_row(result)

    def get_account_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        result = (
            self.client.table("bank_accounts")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return self._single_row(result)

    def list_account_transfers(self, *, account_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
        end = offset + limit - 1
        query = (
            self.client.table("transfer_requests")
            .select("*")
            .or_(f"sender_account_id.eq.{account_id},receiver_account_id.eq.{account_id}")
            .order("created_at", desc=True)
            .range(offset, end)
        )
        result = query.execute()
        return self._rows(result)

    def get_transfer_request_by_id(self, transfer_request_id: str) -> dict[str, Any] | None:
        result = (
            self.client.table("transfer_requests")
            .select("*")
            .eq("id", transfer_request_id)
            .limit(1)
            .execute()
        )
        return self._single_row(result)

    def update_transfer_request_status(self, *, transfer_request_id: str, status: str) -> dict[str, Any] | None:
        timestamp = _utcnow_iso()
        try:
            result = (
                self.client.table("transfer_requests")
                .update({"status": status, "updated_at": timestamp})
                .eq("id", transfer_request_id)
                .execute()
            )
        except Exception as exc:
            raise DatabaseError(f"Failed to update transfer request status: {exc}") from exc
        return self._single_row(result)

    def get_account_by_id(self, account_id: str) -> dict[str, Any] | None:
        result = (
            self.client.table("bank_accounts")
            .select("*")
            .eq("id", account_id)
            .limit(1)
            .execute()
        )
        return self._single_row(result)

    def create_transfer_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self.client.table("transfer_requests").insert(payload).execute()
        except Exception as exc:
            raise DatabaseError(f"Failed to create transfer request: {exc}") from exc
        transfer_row = self._single_row(result)
        if not transfer_row:
            raise DatabaseError("Transfer request creation returned no data.")
        return transfer_row

    def execute_low_risk_transfer(
        self,
        *,
        transfer_request_id: str,
        sender_account_id: str,
        receiver_account_id: str,
        amount: float,
        note: str | None,
    ) -> dict[str, Any]:
        rpc_payload = {
            "p_transfer_request_id": transfer_request_id,
            "p_sender_account_id": sender_account_id,
            "p_receiver_account_id": receiver_account_id,
            "p_amount": amount,
            "p_note": note,
        }
        try:
            result = self.client.rpc("execute_low_risk_transfer", rpc_payload).execute()
        except Exception as exc:
            raise DatabaseError(f"Low-risk transfer posting failed: {exc}") from exc

        row = self._single_row(result)
        if not row:
            raise DatabaseError("Low-risk transfer posting returned no payload.")
        return row

    def upsert_transfer_mfa_challenge(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = (
                self.client.table("transfer_mfa_challenges")
                .upsert(payload, on_conflict="transfer_request_id")
                .execute()
            )
        except Exception as exc:
            raise DatabaseError(f"Failed to upsert transfer MFA challenge: {exc}") from exc

        challenge_row = self._single_row(result)
        if challenge_row:
            return challenge_row
        return payload

    def get_transfer_mfa_challenge(self, transfer_request_id: str) -> dict[str, Any] | None:
        result = (
            self.client.table("transfer_mfa_challenges")
            .select("*")
            .eq("transfer_request_id", transfer_request_id)
            .limit(1)
            .execute()
        )
        return self._single_row(result)

    def update_transfer_mfa_challenge(
        self,
        *,
        transfer_request_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        patch_payload = dict(updates)
        patch_payload["updated_at"] = _utcnow_iso()
        try:
            result = (
                self.client.table("transfer_mfa_challenges")
                .update(patch_payload)
                .eq("transfer_request_id", transfer_request_id)
                .execute()
            )
        except Exception as exc:
            raise DatabaseError(f"Failed to update transfer MFA challenge: {exc}") from exc
        return self._single_row(result)

    def block_user_and_account(self, *, user_id: str, account_id: str) -> None:
        timestamp = _utcnow_iso()
        try:
            (
                self.client.table("bank_users")
                .update({"status": "BLOCKED", "updated_at": timestamp})
                .eq("id", user_id)
                .execute()
            )
            (
                self.client.table("bank_accounts")
                .update({"is_active": False, "updated_at": timestamp})
                .eq("id", account_id)
                .execute()
            )
        except Exception as exc:
            raise DatabaseError(f"Failed to block user account: {exc}") from exc

    def unblock_user_and_account(self, *, user_id: str) -> dict[str, Any]:
        timestamp = _utcnow_iso()
        try:
            (
                self.client.table("bank_users")
                .update({"status": "ACTIVE", "updated_at": timestamp})
                .eq("id", user_id)
                .execute()
            )
            (
                self.client.table("bank_accounts")
                .update({"is_active": True, "updated_at": timestamp})
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            raise DatabaseError(f"Failed to unblock user account: {exc}") from exc

        profile = self.get_user_profile(user_id)
        account = self.get_account_by_user_id(user_id)
        if not profile or not account:
            raise DatabaseError("Unblock succeeded but user profile/account could not be loaded.")
        return {"profile": profile, "account": account}

    @staticmethod
    def _extract_seed_payload(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            nested = value.get("seed_demo_banking_data_for_user")
            if isinstance(nested, dict):
                return nested
            return value

        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                nested = first.get("seed_demo_banking_data_for_user")
                if isinstance(nested, dict):
                    return nested
                return first

        return None

    @classmethod
    def _extract_seed_payload_from_exception(cls, exc: Exception) -> dict[str, Any] | None:
        raw_error = str(exc).strip()
        if not raw_error:
            return None

        candidates = [raw_error]
        start_index = raw_error.find("{")
        end_index = raw_error.rfind("}")
        if start_index != -1 and end_index != -1 and end_index > start_index:
            candidates.append(raw_error[start_index : end_index + 1])

        for candidate in candidates:
            try:
                parsed = ast.literal_eval(candidate)
            except (ValueError, SyntaxError):
                continue

            payload = cls._extract_seed_payload(parsed)
            if isinstance(payload, dict) and "seeded" in payload:
                return payload
        return None

    def seed_demo_data_for_user(self, *, user_id: str, email: str | None) -> dict[str, Any]:
        rpc_payload = {
            "p_user_id": user_id,
            "p_email": email,
            "p_bank_code": self.config.default_bank_code,
        }
        try:
            result = self.client.rpc("seed_demo_banking_data_for_user", rpc_payload).execute()
        except Exception as exc:
            parsed_payload = self._extract_seed_payload_from_exception(exc)
            if parsed_payload:
                return parsed_payload
            raise DatabaseError(f"Failed to seed demo banking data: {exc}") from exc

        payload = self._extract_seed_payload(getattr(result, "data", None))
        if payload:
            return payload

        # Fallback for RPC responses without JSON payload; return an inferred success body.
        account_bundle = self.get_or_create_user_account(user_id=user_id, email=email)
        account = account_bundle["account"]
        transfers = self.list_account_transfers(account_id=str(account["id"]), limit=200, offset=0)
        completed = sum(1 for row in transfers if row.get("status") == "COMPLETED")
        pending_mfa = sum(1 for row in transfers if row.get("status") == "MFA_REQUIRED")
        blocked = sum(1 for row in transfers if row.get("status") == "REJECTED_HIGH_RISK")

        return {
            "seeded": True,
            "message": "Demo banking data seeded.",
            "sender_account_number": str(account["account_number"]),
            "bank_code": str(account["bank_code"]),
            "sender_balance": float(account["balance"]),
            "transfers_seeded": len(transfers),
            "completed_transfers": completed,
            "pending_mfa_transfers": pending_mfa,
            "blocked_transfers": blocked,
        }
