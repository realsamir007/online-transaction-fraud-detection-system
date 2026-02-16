from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

import app.main as main_module
from app.model_loader import ModelArtifacts
from app.rate_limit import RateLimitSettings
from app.risk_engine import RiskThresholds
from app.security import AdminAuthSettings, AuthMode, AuthSettings


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

ADMIN_HEADERS = {"X-Admin-Key": "admin-secret-key"}


class FakeScaler:
    def transform(self, array: np.ndarray) -> np.ndarray:
        return array


class FakeModel:
    def predict_proba(self, _: np.ndarray) -> np.ndarray:
        return np.array([[0.97, 0.03]], dtype=np.float64)


class FakeTransactionRepository:
    def __init__(self) -> None:
        self.client = object()

    def insert_transaction(self, payload: dict) -> None:
        _ = payload


class FakeBankingRepository:
    def __init__(self) -> None:
        self.profile = {
            "id": "user-123",
            "email": "user@example.com",
            "status": "BLOCKED",
            "full_name": "Blocked User",
        }
        self.account = {
            "id": "acc-123",
            "user_id": "user-123",
            "account_number": "1111222233",
            "bank_code": "CAPBANK001",
            "is_active": False,
            "balance": 1000.0,
            "currency": "USD",
        }
        self.unblock_calls = 0

    def get_user_profile(self, user_id: str) -> dict | None:
        if user_id == self.profile["id"]:
            return dict(self.profile)
        return None

    def get_user_profile_by_email(self, email: str) -> dict | None:
        if email.lower() == str(self.profile["email"]).lower():
            return dict(self.profile)
        return None

    def unblock_user_and_account(self, *, user_id: str) -> dict:
        if user_id != self.profile["id"]:
            raise RuntimeError("Unexpected user id")
        self.unblock_calls += 1
        self.profile["status"] = "ACTIVE"
        self.account["is_active"] = True
        return {"profile": dict(self.profile), "account": dict(self.account)}


@contextmanager
def admin_test_client(admin_keys: tuple[str, ...] = ("admin-secret-key",)):
    artifacts = ModelArtifacts(model=FakeModel(), scaler=FakeScaler(), feature_names=FEATURE_NAMES)
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
                lambda: AuthSettings(mode=AuthMode.HYBRID, api_keys=("test-api-key",)),
            ):
                with patch.object(
                    main_module,
                    "load_admin_auth_settings",
                    lambda: AdminAuthSettings(api_keys=admin_keys),
                ):
                    with patch.object(main_module, "SupabaseUserTokenVerifier", lambda client: object()):
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
                                with patch.object(main_module, "_load_demo_seed_enabled", lambda: False):
                                    with patch.object(
                                        main_module,
                                        "_load_mfa_settings",
                                        lambda: main_module.MfaSettings(
                                            code_ttl_seconds=300,
                                            max_attempts=3,
                                            code_length=6,
                                            enable_demo_code_in_response=True,
                                            signing_secret="test-secret",
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
                                                    yield client, banking_repository


class BankingAdminApiTests(unittest.TestCase):
    def test_admin_unblock_by_email_success(self) -> None:
        with admin_test_client() as (client, repository):
            response = client.post(
                "/banking/admin/unblock-user",
                json={"email": "user@example.com"},
                headers=ADMIN_HEADERS,
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user_status"], "ACTIVE")
        self.assertTrue(body["account_active"])
        self.assertEqual(repository.unblock_calls, 1)

    def test_admin_unblock_missing_credentials(self) -> None:
        with admin_test_client() as (client, repository):
            response = client.post("/banking/admin/unblock-user", json={"email": "user@example.com"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(repository.unblock_calls, 0)

    def test_admin_unblock_not_configured(self) -> None:
        with admin_test_client(admin_keys=tuple()) as (client, repository):
            response = client.post(
                "/banking/admin/unblock-user",
                json={"email": "user@example.com"},
                headers=ADMIN_HEADERS,
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(repository.unblock_calls, 0)


if __name__ == "__main__":
    unittest.main()
