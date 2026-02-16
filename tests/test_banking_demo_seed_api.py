from __future__ import annotations

import unittest
from contextlib import contextmanager
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
        self.seed_calls: list[tuple[str, str | None]] = []

    def seed_demo_data_for_user(self, *, user_id: str, email: str | None) -> dict:
        self.seed_calls.append((user_id, email))
        return {
            "seeded": True,
            "message": "Demo data seeded.",
            "sender_account_number": "1234567890",
            "bank_code": "CAPBANK001",
            "sender_balance": 21900.0,
            "transfers_seeded": 6,
            "completed_transfers": 4,
            "pending_mfa_transfers": 1,
            "blocked_transfers": 1,
        }


class FakeTokenVerifier:
    def verify_access_token(self, access_token: str) -> dict:
        if access_token != "valid-jwt-token":
            raise HTTPException(status_code=401, detail="Invalid or expired Bearer token.")
        return {"id": "user-123", "email": "user@example.com"}


@contextmanager
def demo_seed_test_client(enable_demo_seeding: bool = True):
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
                lambda: AuthSettings(mode=AuthMode.JWT, api_keys=tuple()),
            ):
                with patch.object(
                    main_module,
                    "SupabaseUserTokenVerifier",
                    lambda client: FakeTokenVerifier(),
                ):
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
                                lambda: enable_demo_seeding,
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


class BankingDemoSeedApiTests(unittest.TestCase):
    def test_demo_seed_success(self) -> None:
        with demo_seed_test_client(enable_demo_seeding=True) as (client, banking_repository):
            response = client.post("/banking/demo/seed", headers=JWT_AUTH_HEADERS)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["seeded"])
        self.assertEqual(body["sender_account_number"], "1234567890")
        self.assertEqual(body["bank_code"], "CAPBANK001")
        self.assertEqual(body["transfers_seeded"], 6)
        self.assertEqual(banking_repository.seed_calls, [("user-123", "user@example.com")])

    def test_demo_seed_disabled(self) -> None:
        with demo_seed_test_client(enable_demo_seeding=False) as (client, banking_repository):
            response = client.post("/banking/demo/seed", headers=JWT_AUTH_HEADERS)

        self.assertEqual(response.status_code, 403)
        self.assertIn("disabled", response.json()["detail"].lower())
        self.assertEqual(banking_repository.seed_calls, [])

    def test_demo_seed_requires_jwt(self) -> None:
        with demo_seed_test_client(enable_demo_seeding=True) as (client, _):
            response = client.post("/banking/demo/seed")

        self.assertEqual(response.status_code, 401)
        self.assertIn("bearer token", response.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
