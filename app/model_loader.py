from __future__ import annotations

import json
import os
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


def _load_joblib_artifact(path: Path, artifact_name: str) -> Any:
    try:
        return joblib.load(path)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load {artifact_name} from {path}. "
            "This is commonly caused by a scikit-learn version mismatch between training and runtime."
        ) from exc


def load_artifacts(models_dir: Path) -> ModelArtifacts:
    default_model_filename = (
        "random_forest_model_v1.joblib"
        if (models_dir / "random_forest_model_v1.joblib").exists()
        else "random_forest_model.joblib"
    )
    default_scaler_filename = (
        "scaler_v1.joblib"
        if (models_dir / "scaler_v1.joblib").exists()
        else "scaler.joblib"
    )

    model_filename = os.getenv("MODEL_FILENAME", default_model_filename).strip()
    scaler_filename = os.getenv("SCALER_FILENAME", default_scaler_filename).strip()
    feature_names_filename = os.getenv("FEATURE_NAMES_FILENAME", "feature_names.json").strip()

    if not model_filename:
        raise ValueError("MODEL_FILENAME must not be empty.")
    if not scaler_filename:
        raise ValueError("SCALER_FILENAME must not be empty.")
    if not feature_names_filename:
        raise ValueError("FEATURE_NAMES_FILENAME must not be empty.")

    model_path = models_dir / model_filename
    scaler_path = models_dir / scaler_filename
    feature_names_path = models_dir / feature_names_filename

    for artifact_path in (model_path, scaler_path, feature_names_path):
        if not artifact_path.exists():
            raise FileNotFoundError(f"Required artifact not found: {artifact_path}")

    model = _load_joblib_artifact(model_path, "model")
    scaler = _load_joblib_artifact(scaler_path, "scaler")

    with feature_names_path.open("r", encoding="utf-8") as feature_file:
        feature_names = _validate_feature_names(json.load(feature_file))

    _validate_feature_count("Model", len(feature_names), getattr(model, "n_features_in_", None))
    _validate_feature_count("Scaler", len(feature_names), getattr(scaler, "n_features_in_", None))

    if not hasattr(model, "predict_proba"):
        raise TypeError("Loaded model does not support probability predictions with predict_proba().")

    return ModelArtifacts(model=model, scaler=scaler, feature_names=feature_names)
