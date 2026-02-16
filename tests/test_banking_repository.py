from __future__ import annotations

import unittest

from app.banking_repository import BankingConfig, BankingRepository
from app.database import DatabaseError


class FakeRpcCall:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    def execute(self):
        if self._error is not None:
            raise self._error
        return self._result


class FakeRpcResult:
    def __init__(self, data) -> None:
        self.data = data


class FakeClient:
    def __init__(self, *, rpc_result=None, rpc_error: Exception | None = None) -> None:
        self.rpc_result = rpc_result
        self.rpc_error = rpc_error
        self.last_rpc_fn = None
        self.last_rpc_payload = None

    def rpc(self, fn: str, payload: dict):
        self.last_rpc_fn = fn
        self.last_rpc_payload = payload
        return FakeRpcCall(result=self.rpc_result, error=self.rpc_error)


class BankingRepositoryTests(unittest.TestCase):
    def test_seed_demo_data_parses_payload_from_exception_string(self) -> None:
        payload_text = (
            "{'seeded': True, 'message': 'Demo banking data seeded for this user.', "
            "'bank_code': 'CAPBANK001', 'sender_balance': 21900.0, 'transfers_seeded': 6, "
            "'blocked_transfers': 1, 'completed_transfers': 4, 'pending_mfa_transfers': 1, "
            "'sender_account_number': '5282916446'}"
        )
        fake_client = FakeClient(rpc_error=RuntimeError(payload_text))
        repo = BankingRepository(client=fake_client, config=BankingConfig())

        result = repo.seed_demo_data_for_user(user_id="user-123", email="user@example.com")

        self.assertTrue(result["seeded"])
        self.assertEqual(result["bank_code"], "CAPBANK001")
        self.assertEqual(result["transfers_seeded"], 6)
        self.assertEqual(result["sender_account_number"], "5282916446")
        self.assertEqual(fake_client.last_rpc_fn, "seed_demo_banking_data_for_user")

    def test_seed_demo_data_returns_payload_from_rpc_data(self) -> None:
        rpc_payload = {
            "seeded": True,
            "message": "ok",
            "sender_account_number": "1111222233",
            "bank_code": "CAPBANK001",
            "sender_balance": 100.0,
            "transfers_seeded": 6,
            "completed_transfers": 4,
            "pending_mfa_transfers": 1,
            "blocked_transfers": 1,
        }
        fake_client = FakeClient(rpc_result=FakeRpcResult(rpc_payload))
        repo = BankingRepository(client=fake_client, config=BankingConfig())

        result = repo.seed_demo_data_for_user(user_id="user-abc", email=None)

        self.assertEqual(result["message"], "ok")
        self.assertEqual(result["sender_balance"], 100.0)

    def test_seed_demo_data_unknown_rpc_error_raises_database_error(self) -> None:
        fake_client = FakeClient(rpc_error=RuntimeError("unexpected rpc failure"))
        repo = BankingRepository(client=fake_client, config=BankingConfig())

        with self.assertRaises(DatabaseError):
            repo.seed_demo_data_for_user(user_id="user-xyz", email=None)


if __name__ == "__main__":
    unittest.main()
