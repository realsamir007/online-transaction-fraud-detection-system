from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

import app.main as main_module
from app.database import DatabaseError
from app.model_loader import ModelArtifacts
from app.rate_limit import RateLimitSettings
from app.risk_engine import RiskThresholds


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


VALID_PAYLOAD = {
    "step": 1,
    "amount": 1000.0,
    "oldbalanceOrg": 5000.0,
    "newbalanceOrig": 4000.0,
    "oldbalanceDest": 10000.0,
    "newbalanceDest": 11000.0,
    "hour": 2,
    "is_night": True,
    "amount_ratio": 0.2,
    "sender_balance_change": -1000.0,
    "receiver_balance_change": 1000.0,
    "orig_balance_zero": False,
    "dest_balance_zero": False,
    "type_TRANSFER": True,
}

AUTH_HEADERS = {"X-API-Key": "test-api-key"}


class FakeScaler:
    def __init__(self) -> None:
        self.last_input: np.ndarray | None = None

    def transform(self, array: np.ndarray) -> np.ndarray:
        self.last_input = array
        return array


class FakeModel:
    def __init__(self, fraud_probability: float) -> None:
        self.fraud_probability = fraud_probability

    def predict_proba(self, _: np.ndarray) -> np.ndarray:
        return np.array(
            [[1.0 - self.fraud_probability, self.fraud_probability]],
            dtype=np.float64,
        )


class FakeRepository:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.rows: list[dict] = []

    def insert_transaction(self, payload: dict) -> None:
        if self.should_fail:
            raise DatabaseError("forced insert failure for test")
        self.rows.append(payload)


@contextmanager
def test_client(
    fraud_probability: float = 0.03,
    db_should_fail: bool = False,
    thresholds: RiskThresholds | None = None,
    rate_limit_settings: RateLimitSettings | None = None,
):
    scaler = FakeScaler()
    model = FakeModel(fraud_probability=fraud_probability)
    repository = FakeRepository(should_fail=db_should_fail)
    artifacts = ModelArtifacts(model=model, scaler=scaler, feature_names=FEATURE_NAMES)

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
            with patch.object(main_module, "load_api_keys", lambda: ("test-api-key",)):
                with patch.object(
                    main_module,
                    "_load_risk_thresholds",
                    lambda: thresholds or RiskThresholds(low=0.30, high=0.70),
                ):
                    with patch.object(
                        main_module,
                        "_load_rate_limit_settings",
                        lambda: rate_limit_settings or RateLimitSettings(enabled=True, requests=60, window_seconds=60),
                    ):
                        with patch.object(main_module, "SupabaseTransactionRepository", lambda config: repository):
                            with TestClient(main_module.app) as client:
                                yield client, scaler, repository


class FraudApiTests(unittest.TestCase):
    def test_health_endpoint(self) -> None:
        with test_client() as (client, _, _):
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "model_version": "random_forest_v1",
                "service": "fraud-detection-backend",
            },
        )

    def test_predict_transaction_success(self) -> None:
        payload = dict(VALID_PAYLOAD)
        with test_client(fraud_probability=0.82) as (client, scaler, repository):
            response = client.post("/predict-transaction", json=payload, headers=AUTH_HEADERS)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertAlmostEqual(body["fraud_probability"], 0.82, places=9)
        self.assertEqual(body["risk_level"], "HIGH")
        self.assertEqual(body["action"], "BLOCK")
        self.assertEqual(body["message"], "Transaction blocked due to high fraud risk")
        self.assertEqual(body["model_version"], "random_forest_v1")

        self.assertEqual(len(repository.rows), 1)
        self.assertAlmostEqual(repository.rows[0]["fraud_probability"], 0.82, places=9)
        self.assertEqual(repository.rows[0]["risk_level"], "HIGH")
        self.assertEqual(repository.rows[0]["action"], "BLOCK")

        expected_ordered_features = np.asarray(
            [[payload[feature_name] for feature_name in FEATURE_NAMES]],
            dtype=np.float64,
        )
        np.testing.assert_allclose(scaler.last_input, expected_ordered_features)

    def test_predict_transaction_invalid_payload(self) -> None:
        payload = dict(VALID_PAYLOAD)
        payload["hour"] = 24

        with test_client() as (client, _, repository):
            response = client.post("/predict-transaction", json=payload, headers=AUTH_HEADERS)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(repository.rows), 0)

    def test_predict_transaction_database_failure(self) -> None:
        with test_client(fraud_probability=0.45, db_should_fail=True) as (client, _, _):
            response = client.post("/predict-transaction", json=VALID_PAYLOAD, headers=AUTH_HEADERS)

        self.assertEqual(response.status_code, 500)
        self.assertIn("forced insert failure for test", response.json()["detail"])

    def test_predict_transaction_unauthorized(self) -> None:
        with test_client() as (client, _, repository):
            response = client.post("/predict-transaction", json=VALID_PAYLOAD)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(len(repository.rows), 0)

    def test_predict_transaction_custom_thresholds(self) -> None:
        custom_thresholds = RiskThresholds(low=0.20, high=0.90)
        with test_client(fraud_probability=0.82, thresholds=custom_thresholds) as (client, _, _):
            response = client.post("/predict-transaction", json=VALID_PAYLOAD, headers=AUTH_HEADERS)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["risk_level"], "MEDIUM")
        self.assertEqual(body["action"], "TRIGGER_MFA")

    def test_health_has_request_id_header(self) -> None:
        with test_client() as (client, _, _):
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("x-request-id"))

    def test_predict_transaction_echoes_request_id_header(self) -> None:
        request_id = "req-12345"
        with test_client(fraud_probability=0.82) as (client, _, _):
            response = client.post(
                "/predict-transaction",
                json=VALID_PAYLOAD,
                headers={**AUTH_HEADERS, "X-Request-ID": request_id},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-request-id"), request_id)

    def test_predict_transaction_rate_limited(self) -> None:
        strict_limit = RateLimitSettings(enabled=True, requests=1, window_seconds=60)
        with test_client(fraud_probability=0.82, rate_limit_settings=strict_limit) as (client, _, _):
            first = client.post("/predict-transaction", json=VALID_PAYLOAD, headers=AUTH_HEADERS)
            second = client.post("/predict-transaction", json=VALID_PAYLOAD, headers=AUTH_HEADERS)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["detail"], "Rate limit exceeded. Please retry later.")
        self.assertTrue(second.headers.get("retry-after"))


if __name__ == "__main__":
    unittest.main()
