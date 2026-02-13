from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import numpy as np
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app.database import DatabaseError, SupabaseConfig, SupabaseTransactionRepository
from app.model_loader import load_artifacts
from app.rate_limit import InMemoryRateLimiter, RateLimitSettings, enforce_prediction_rate_limit
from app.risk_engine import RiskThresholds, evaluate_risk
from app.security import load_api_keys, require_prediction_api_key

load_dotenv()

DEFAULT_MODEL_VERSION = "random_forest_v1"
DEFAULT_LOW_THRESHOLD = 0.30
DEFAULT_HIGH_THRESHOLD = 0.70
DEFAULT_RATE_LIMIT_ENABLED = True
DEFAULT_RATE_LIMIT_REQUESTS = 60
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_LOG_LEVEL = "INFO"
REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger("fraud_detection_api")


def _configure_logging() -> None:
    log_level_name = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper() or DEFAULT_LOG_LEVEL
    log_level = getattr(logging, log_level_name, logging.INFO)

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    else:
        logging.getLogger().setLevel(log_level)

    logger.setLevel(log_level)


_configure_logging()


class TransactionFeatures(BaseModel):
    step: int = Field(..., ge=0)
    amount: float = Field(..., ge=0.0)
    oldbalanceOrg: float = Field(..., ge=0.0)
    newbalanceOrig: float = Field(..., ge=0.0)
    oldbalanceDest: float = Field(..., ge=0.0)
    newbalanceDest: float = Field(..., ge=0.0)
    hour: int = Field(..., ge=0, le=23)
    is_night: bool
    amount_ratio: float = Field(..., ge=0.0)
    sender_balance_change: float
    receiver_balance_change: float
    orig_balance_zero: bool
    dest_balance_zero: bool
    type_TRANSFER: bool

    model_config = ConfigDict(extra="forbid")


class PredictionResponse(BaseModel):
    fraud_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    action: Literal["APPROVE", "TRIGGER_MFA", "BLOCK"]
    message: str
    model_version: str


def _parse_cors_origins(raw_origins: str | None) -> list[str]:
    if not raw_origins:
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    if raw_origins.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def _prepare_feature_array(payload: TransactionFeatures, feature_names: list[str]) -> tuple[np.ndarray, dict]:
    input_dict = payload.model_dump()
    missing_features = [feature for feature in feature_names if feature not in input_dict]
    if missing_features:
        raise ValueError(f"Incoming payload is missing required model features: {missing_features}")

    ordered_features = [input_dict[feature] for feature in feature_names]
    feature_array = np.asarray([ordered_features], dtype=np.float64)
    return feature_array, input_dict


def _load_risk_thresholds() -> RiskThresholds:
    raw_low = os.getenv("LOW_THRESHOLD", str(DEFAULT_LOW_THRESHOLD)).strip()
    raw_high = os.getenv("HIGH_THRESHOLD", str(DEFAULT_HIGH_THRESHOLD)).strip()
    try:
        low = float(raw_low)
        high = float(raw_high)
    except ValueError as exc:
        raise ValueError("LOW_THRESHOLD and HIGH_THRESHOLD must be numeric values.") from exc

    return RiskThresholds(low=low, high=high)


def _parse_bool_env(raw_value: str | None, default: bool) -> bool:
    if raw_value is None or not raw_value.strip():
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("RATE_LIMIT_ENABLED must be a boolean value (true/false).")


def _load_rate_limit_settings() -> RateLimitSettings:
    enabled = _parse_bool_env(os.getenv("RATE_LIMIT_ENABLED"), DEFAULT_RATE_LIMIT_ENABLED)
    raw_requests = os.getenv("RATE_LIMIT_REQUESTS", str(DEFAULT_RATE_LIMIT_REQUESTS)).strip()
    raw_window_seconds = os.getenv("RATE_LIMIT_WINDOW_SECONDS", str(DEFAULT_RATE_LIMIT_WINDOW_SECONDS)).strip()

    try:
        requests = int(raw_requests)
        window_seconds = int(raw_window_seconds)
    except ValueError as exc:
        raise ValueError(
            "RATE_LIMIT_REQUESTS and RATE_LIMIT_WINDOW_SECONDS must be integer values."
        ) from exc

    return RateLimitSettings(enabled=enabled, requests=requests, window_seconds=window_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_root = Path(__file__).resolve().parent.parent
    models_dir = project_root / "models"
    model_version = os.getenv("MODEL_VERSION", DEFAULT_MODEL_VERSION).strip() or DEFAULT_MODEL_VERSION

    artifacts = load_artifacts(models_dir=models_dir)
    repository = SupabaseTransactionRepository(config=SupabaseConfig.from_env())
    prediction_api_keys = load_api_keys()
    risk_thresholds = _load_risk_thresholds()
    rate_limit_settings = _load_rate_limit_settings()
    rate_limiter = InMemoryRateLimiter(settings=rate_limit_settings)

    app.state.model = artifacts.model
    app.state.scaler = artifacts.scaler
    app.state.feature_names = artifacts.feature_names
    app.state.model_version = model_version
    app.state.transaction_repo = repository
    app.state.prediction_api_keys = prediction_api_keys
    app.state.risk_thresholds = risk_thresholds
    app.state.rate_limit_settings = rate_limit_settings
    app.state.rate_limiter = rate_limiter

    yield


app = FastAPI(
    title="Real-Time Transaction Fraud Detection API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(os.getenv("CORS_ALLOWED_ORIGINS")),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_and_logging_middleware(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER, "").strip() or str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start_time) * 1000
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "request_complete request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "model_version": app.state.model_version,
        "service": "fraud-detection-backend",
    }


@app.post("/predict-transaction", response_model=PredictionResponse)
def predict_transaction(
    request: Request,
    payload: TransactionFeatures,
    _: None = Depends(require_prediction_api_key),
    __: None = Depends(enforce_prediction_rate_limit),
) -> PredictionResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        feature_array, raw_input = _prepare_feature_array(payload, app.state.feature_names)
        scaled_features = app.state.scaler.transform(feature_array)
        probabilities = app.state.model.predict_proba(scaled_features)

        if probabilities.shape[1] < 2:
            raise RuntimeError("Model probability output format is invalid.")

        fraud_probability = float(probabilities[0][1])
        decision = evaluate_risk(fraud_probability, app.state.risk_thresholds)

        db_record = {
            **raw_input,
            "fraud_probability": fraud_probability,
            "risk_level": decision.risk_level,
            "action": decision.action,
        }
        app.state.transaction_repo.insert_transaction(db_record)
        logger.info(
            "prediction_scored request_id=%s fraud_probability=%.6f risk_level=%s action=%s",
            request_id,
            fraud_probability,
            decision.risk_level,
            decision.action,
        )

        return PredictionResponse(
            fraud_probability=fraud_probability,
            risk_level=decision.risk_level,
            action=decision.action,
            message=decision.message,
            model_version=app.state.model_version,
        )
    except DatabaseError as exc:
        logger.error("prediction_db_error request_id=%s error=%s", request_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("prediction_validation_error request_id=%s error=%s", request_id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("prediction_internal_error request_id=%s", request_id)
        raise HTTPException(status_code=500, detail="Internal server error during transaction scoring.") from exc
