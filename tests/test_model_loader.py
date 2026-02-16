from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np

from app.model_loader import load_artifacts


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


class FakeModel:
    n_features_in_ = len(FEATURE_NAMES)

    def predict_proba(self, _: np.ndarray) -> np.ndarray:
        return np.array([[0.9, 0.1]], dtype=np.float64)


class FakeScaler:
    n_features_in_ = len(FEATURE_NAMES)

    def transform(self, array: np.ndarray) -> np.ndarray:
        return array


class ModelLoaderTests(unittest.TestCase):
    def test_load_artifacts_prefers_v1_filenames_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            joblib.dump(FakeModel(), models_dir / "random_forest_model_v1.joblib")
            joblib.dump(FakeScaler(), models_dir / "scaler_v1.joblib")
            (models_dir / "feature_names.json").write_text(json.dumps(FEATURE_NAMES), encoding="utf-8")

            with patch.dict("os.environ", {}, clear=False):
                os.environ.pop("MODEL_FILENAME", None)
                os.environ.pop("SCALER_FILENAME", None)
                os.environ["FEATURE_NAMES_FILENAME"] = "feature_names.json"
                artifacts = load_artifacts(models_dir)

        self.assertEqual(artifacts.feature_names, FEATURE_NAMES)
        self.assertTrue(hasattr(artifacts.model, "predict_proba"))

    def test_load_artifacts_uses_configured_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            joblib.dump(FakeModel(), models_dir / "rf_custom.joblib")
            joblib.dump(FakeScaler(), models_dir / "scaler_custom.joblib")
            (models_dir / "feature_custom.json").write_text(json.dumps(FEATURE_NAMES), encoding="utf-8")

            with patch.dict(
                "os.environ",
                {
                    "MODEL_FILENAME": "rf_custom.joblib",
                    "SCALER_FILENAME": "scaler_custom.joblib",
                    "FEATURE_NAMES_FILENAME": "feature_custom.json",
                },
                clear=False,
            ):
                artifacts = load_artifacts(models_dir)

        self.assertEqual(artifacts.feature_names, FEATURE_NAMES)
        self.assertTrue(hasattr(artifacts.model, "predict_proba"))


if __name__ == "__main__":
    unittest.main()
