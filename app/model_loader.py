from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib


@dataclass(frozen=True)
class ModelArtifacts:
    model: Any
    scaler: Any
    feature_names: list[str]


def _validate_feature_names(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("feature_names.json must contain a non-empty array of feature names.")

    if not all(isinstance(item, str) and item.strip() for item in raw_value):
        raise ValueError("feature_names.json must contain only non-empty string entries.")

    return raw_value


def _validate_feature_count(artifact_name: str, expected: int, actual: int | None) -> None:
    if actual is None:
        return
    if expected != actual:
        raise ValueError(
            f"{artifact_name} expects {actual} features, but feature_names.json defines {expected}."
        )


def load_artifacts(models_dir: Path) -> ModelArtifacts:
    model_path = models_dir / "random_forest_model.joblib"
    scaler_path = models_dir / "scaler.joblib"
    feature_names_path = models_dir / "feature_names.json"

    for artifact_path in (model_path, scaler_path, feature_names_path):
        if not artifact_path.exists():
            raise FileNotFoundError(f"Required artifact not found: {artifact_path}")

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    with feature_names_path.open("r", encoding="utf-8") as feature_file:
        feature_names = _validate_feature_names(json.load(feature_file))

    _validate_feature_count("Model", len(feature_names), getattr(model, "n_features_in_", None))
    _validate_feature_count("Scaler", len(feature_names), getattr(scaler, "n_features_in_", None))

    if not hasattr(model, "predict_proba"):
        raise TypeError("Loaded model does not support probability predictions with predict_proba().")

    return ModelArtifacts(model=model, scaler=scaler, feature_names=feature_names)

