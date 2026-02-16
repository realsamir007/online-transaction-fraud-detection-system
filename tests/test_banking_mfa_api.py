from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main_module
from app.model_loader import ModelArtifacts
from app.rate_limit import RateLimitSettings
from app.risk_engine import RiskThresholds
from app.security import AuthMode, AuthSettings


FEATURE_NAMES = [
    "step",
    "amount",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "hour",
    "is_night",
    "amount_ratio",
    "sender_balance_change",
    "receiver_balance_change",
    "orig_balance_zero",
    "dest_balance_zero",
    "type_TRANSFER",
]

JWT_AUTH_HEADERS = {"Authorization": "Bearer valid-jwt-token"}

TRANSFER_PAYLOAD = {
    "receiver_account_number": "9999000011",
    "receiver_bank_code": "CAPBANK001",
    "amount": 1200.0,
    "note": "MFA transfer test",
}


class FakeScaler:
    def transform(self, array: np.ndarray) -> np.ndarray:
        return array


class FakeModel:
    def __init__(self, fraud_probability: float) -> None:
        self.fraud_probability = fraud_probability

    def predict_proba(self, _: np.ndarray) -> np.ndarray:
        return np.array([[1.0 - self.fraud_probability, self.fraud_probability]], dtype=np.float64)


class FakeTransactionRepository:
    def __init__(self) -> None:
        self.client = object()
        self.rows: list[dict] = []

    def insert_transaction(self, payload: dict) -> None:
        self.rows.append(payload)


class FakeBankingRepository:
    def __init__(self) -> None:
        self.sender_profile = {
            "id": "user-123",
            "email": "user@example.com",
            "full_name": "Test User",
            "status": "ACTIVE",
        }
        self.sender_account = {
            "id": "acc-sender",
            "user_id": "user-123",
            "account_number": "1111222233",
            "bank_code": "CAPBANK001",
            "currency": "USD",
            "balance": 10000.0,
            "is_active": True,
        }
        self.receiver_account = {
            "id": "acc-receiver",
            "user_id": "user-456",
            "account_number": "9999000011",
            "bank_code": "CAPBANK001",
            "currency": "USD",
            "balance": 5000.0,
            "is_active": True,
        }
        self.transfers: dict[str, dict] = {}
        self.challenges: dict[str, dict] = {}
        self._counter = 0

    def get_or_create_user_account(self, user_id: str, email: str | None) -> dict:
        _ = email
        if user_id != "user-123":
            raise RuntimeError("Unexpected user_id")
        return {"profile": dict(self.sender_profile), "account": dict(self.sender_account)}

    def get_account_by_bank_details(self, *, bank_code: str, account_number: str) -> dict | None:
        if bank_code == self.receiver_account["bank_code"] and account_number == self.receiver_account["account_number"]:
            return dict(self.receiver_account)
        return None

    def create_transfer_request(self, payload: dict) -> dict:
        self._counter += 1
        transfer_id = f"tr-{self._counter}"
        row = dict(payload)
        row["id"] = transfer_id
        row["created_at"] = payload.get("created_at", datetime.now(UTC).isoformat())
        row["updated_at"] = payload.get("updated_at", datetime.now(UTC).isoformat())
        self.transfers[transfer_id] = row
        return dict(row)

    def get_transfer_request_by_id(self, transfer_request_id: str) -> dict | None:
        row = self.transfers.get(transfer_request_id)
        return dict(row) if row else None

    def update_transfer_request_status(self, *, transfer_request_id: str, status: str) -> dict | None:
        row = self.transfers.get(transfer_request_id)
        if not row:
            return None
        row["status"] = status
        row["updated_at"] = datetime.now(UTC).isoformat()
        return dict(row)

    def upsert_transfer_mfa_challenge(self, payload: dict) -> dict:
        row = dict(payload)
        self.challenges[payload["transfer_request_id"]] = row
        return dict(row)

    def get_transfer_mfa_challenge(self, transfer_request_id: str) -> dict | None:
        row = self.challenges.get(transfer_request_id)
        return dict(row) if row else None

    def update_transfer_mfa_challenge(self, *, transfer_request_id: str, updates: dict) -> dict | None:
        row = self.challenges.get(transfer_request_id)
        if not row:
            return None
        row.update(updates)
        row["updated_at"] = datetime.now(UTC).isoformat()
        return dict(row)

    def execute_low_risk_transfer(
        self,
        *,
        transfer_request_id: str,
        sender_account_id: str,
        receiver_account_id: str,
        amount: float,
        note: str | None,
    ) -> dict:
        _ = note
        if sender_account_id != self.sender_account["id"] or receiver_account_id != self.receiver_account["id"]:
            raise RuntimeError("Unexpected account IDs for posting")
        self.sender_account["balance"] -= amount
        self.receiver_account["balance"] += amount
        self.transfers[transfer_request_id]["status"] = "COMPLETED"
        return {
            "transfer_request_id": transfer_request_id,
            "sender_balance_after": self.sender_account["balance"],
            "receiver_balance_after": self.receiver_account["balance"],
        }

    def block_user_and_account(self, *, user_id: str, account_id: str) -> None:
        _ = user_id
        _ = account_id


class FakeTokenVerifier:
    def verify_access_token(self, access_token: str) -> dict:
        if access_token != "valid-jwt-token":
            raise HTTPException(status_code=401, detail="Invalid or expired Bearer token.")
        return {"id": "user-123", "email": "user@example.com"}


@contextmanager
def mfa_test_client():
    artifacts = ModelArtifacts(
        model=FakeModel(fraud_probability=0.5),
        scaler=FakeScaler(),
        feature_names=FEATURE_NAMES,
    )
    transaction_repository = FakeTransactionRepository()
    banking_repository = FakeBankingRepository()

    with patch.object(main_module, "load_artifacts", lambda models_dir: artifacts):
        with patch.object(
            main_module.SupabaseConfig,
            "from_env",
            classmethod(
                lambda cls: cls(
                    url="https://example.supabase.co",
                    service_role_key="test-service-role-key",
                    table_name="transactions",
                )
            ),
        ):
            with patch.object(
                main_module,
                "load_auth_settings",
                lambda: AuthSettings(mode=AuthMode.JWT, api_keys=tuple()),
            ):
                with patch.object(main_module, "SupabaseUserTokenVerifier", lambda client: FakeTokenVerifier()):
                    with patch.object(
                        main_module,
                        "_load_risk_thresholds",
                        lambda: RiskThresholds(low=0.30, high=0.70),
                    ):
                        with patch.object(
                            main_module,
                            "_load_rate_limit_settings",
                            lambda: RateLimitSettings(enabled=True, requests=60, window_seconds=60),
                        ):
                            with patch.object(
                                main_module,
                                "_load_demo_seed_enabled",
                                lambda: False,
                            ):
                                with patch.object(
                                    main_module,
                                    "_load_mfa_settings",
                                    lambda: main_module.MfaSettings(
                                        code_ttl_seconds=300,
                                        max_attempts=3,
                                        code_length=6,
                                        enable_demo_code_in_response=True,
                                        signing_secret="test-mfa-secret",
                                    ),
                                ):
                                    with patch.object(
                                        main_module,
                                        "SupabaseTransactionRepository",
                                        lambda config: transaction_repository,
                                    ):
                                        with patch.object(
                                            main_module,
                                            "BankingRepository",
                                            lambda client, config: banking_repository,
                                        ):
                                            with TestClient(main_module.app) as client:
                                                yield client


class BankingMfaApiTests(unittest.TestCase):
    def test_mfa_flow_medium_transfer_to_completed(self) -> None:
        with mfa_test_client() as client:
            initiate = client.post(
                "/banking/transfers/initiate",
                json=TRANSFER_PAYLOAD,
                headers=JWT_AUTH_HEADERS,
            )
            self.assertEqual(initiate.status_code, 200)
            initiate_body = initiate.json()
            self.assertTrue(initiate_body["mfa_required"])
            self.assertEqual(initiate_body["status"], "MFA_REQUIRED")
            transfer_id = initiate_body["transfer_id"]

            challenge = client.post(
                f"/banking/transfers/{transfer_id}/mfa/challenge",
                headers=JWT_AUTH_HEADERS,
            )
            self.assertEqual(challenge.status_code, 200)
            challenge_body = challenge.json()
            self.assertTrue(challenge_body["mfa_required"])
            self.assertTrue(challenge_body["demo_code"])
            self.assertEqual(challenge_body["remaining_attempts"], 3)

            wrong_verify = client.post(
                f"/banking/transfers/{transfer_id}/mfa/verify",
                json={"code": "000000"},
                headers=JWT_AUTH_HEADERS,
            )
            self.assertEqual(wrong_verify.status_code, 401)
            self.assertIn("attempt", wrong_verify.json()["detail"].lower())

            correct_verify = client.post(
                f"/banking/transfers/{transfer_id}/mfa/verify",
                json={"code": challenge_body["demo_code"]},
                headers=JWT_AUTH_HEADERS,
            )
            self.assertEqual(correct_verify.status_code, 200)
            verify_body = correct_verify.json()
            self.assertEqual(verify_body["status"], "COMPLETED")
            self.assertFalse(verify_body["mfa_required"])
            self.assertIn("MFA verified", verify_body["message"])

    def test_mfa_verify_without_challenge_fails(self) -> None:
        with mfa_test_client() as client:
            initiate = client.post(
                "/banking/transfers/initiate",
                json=TRANSFER_PAYLOAD,
                headers=JWT_AUTH_HEADERS,
            )
            self.assertEqual(initiate.status_code, 200)
            transfer_id = initiate.json()["transfer_id"]

            verify = client.post(
                f"/banking/transfers/{transfer_id}/mfa/verify",
                json={"code": "123456"},
                headers=JWT_AUTH_HEADERS,
            )
            self.assertEqual(verify.status_code, 400)
            self.assertIn("challenge", verify.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
