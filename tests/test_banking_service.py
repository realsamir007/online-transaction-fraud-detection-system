from __future__ import annotations

from datetime import UTC, datetime
import unittest

from app.banking_service import (
    build_model_feature_payload,
    compute_transfer_feature_context,
    mask_account_number,
)


class BankingServiceTests(unittest.TestCase):
    def test_feature_payload_is_auto_computed(self) -> None:
        context = compute_transfer_feature_context(
            amount=500.0,
            sender_old_balance=2000.0,
            receiver_old_balance=100.0,
            now=datetime(2026, 2, 14, 2, 15, tzinfo=UTC),
            step=12,
        )
        payload = build_model_feature_payload(context)

        self.assertEqual(payload["step"], 12)
        self.assertEqual(payload["hour"], 2)
        self.assertTrue(payload["is_night"])
        self.assertEqual(payload["oldbalanceOrg"], 2000.0)
        self.assertEqual(payload["newbalanceOrig"], 1500.0)
        self.assertEqual(payload["oldbalanceDest"], 100.0)
        self.assertEqual(payload["newbalanceDest"], 600.0)
        self.assertAlmostEqual(payload["amount_ratio"], 0.25, places=9)
        self.assertEqual(payload["sender_balance_change"], 500.0)
        self.assertEqual(payload["receiver_balance_change"], 500.0)
        self.assertFalse(payload["orig_balance_zero"])
        self.assertFalse(payload["dest_balance_zero"])
        self.assertTrue(payload["type_TRANSFER"])

    def test_compute_feature_context_validates_balance(self) -> None:
        with self.assertRaises(ValueError):
            compute_transfer_feature_context(
                amount=1000.0,
                sender_old_balance=100.0,
                receiver_old_balance=50.0,
            )

    def test_account_masking(self) -> None:
        self.assertEqual(mask_account_number("1234567890"), "******7890")
        self.assertEqual(mask_account_number("9988"), "9988")


if __name__ == "__main__":
    unittest.main()

