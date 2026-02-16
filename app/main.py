from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import logging
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app.banking_repository import BankingConfig, BankingRepository
from app.banking_service import (
    build_model_feature_payload,
    compute_transfer_feature_context,
    mask_account_number,
)
from app.database import DatabaseError, SupabaseConfig, SupabaseTransactionRepository
from app.model_loader import load_artifacts
from app.rate_limit import InMemoryRateLimiter, RateLimitSettings, enforce_prediction_rate_limit
from app.risk_engine import RiskThresholds, evaluate_risk
from app.security import (
    AdminAuthSettings,
    AuthContext,
    SupabaseUserTokenVerifier,
    authenticate_banking_admin_request,
    authenticate_banking_user,
    authenticate_prediction_request,
    load_admin_auth_settings,
    load_auth_settings,
)

load_dotenv()

DEFAULT_MODEL_VERSION = "random_forest_v1"
DEFAULT_LOW_THRESHOLD = 0.10
DEFAULT_HIGH_THRESHOLD = 0.50
DEFAULT_RATE_LIMIT_ENABLED = True
DEFAULT_RATE_LIMIT_REQUESTS = 60
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_ENABLE_DEMO_SEEDING = False
DEFAULT_MFA_CODE_TTL_SECONDS = 300
DEFAULT_MFA_MAX_ATTEMPTS = 3
DEFAULT_MFA_CODE_LENGTH = 6
DEFAULT_ENABLE_DEMO_MFA_CODE_IN_RESPONSE = True
DEFAULT_MFA_SIGNING_SECRET = "change-this-mfa-secret"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_TRANSFER_HISTORY_LIMIT = 20
REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger("fraud_detection_api")


@dataclass(frozen=True)
class MfaSettings:
    code_ttl_seconds: int
    max_attempts: int
    code_length: int
    enable_demo_code_in_response: bool
    signing_secret: str


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


class AccountSummary(BaseModel):
    account_id: str
    account_number: str
    bank_code: str
    currency: str
    balance: float
    is_active: bool


class TransferHistoryItem(BaseModel):
    transfer_id: str
    direction: Literal["INCOMING", "OUTGOING"]
    counterparty_account_number: str
    counterparty_bank_code: str
    amount: float
    status: str
    risk_level: str | None = None
    action: str | None = None
    note: str | None = None
    created_at: datetime


class DashboardResponse(BaseModel):
    account: AccountSummary
    recent_transactions: list[TransferHistoryItem]


class TransactionHistoryResponse(BaseModel):
    items: list[TransferHistoryItem]
    limit: int
    offset: int


class ReceiverValidationRequest(BaseModel):
    receiver_account_number: str = Field(..., min_length=4, max_length=34)
    receiver_bank_code: str = Field(..., min_length=3, max_length=20)

    model_config = ConfigDict(extra="forbid")


class ReceiverValidationResponse(BaseModel):
    exists: bool
    account_holder: str | None = None
    account_number_masked: str | None = None
    bank_code: str | None = None
    message: str


class InitiateTransferRequest(BaseModel):
    receiver_account_number: str = Field(..., min_length=4, max_length=34)
    receiver_bank_code: str = Field(..., min_length=3, max_length=20)
    amount: float = Field(..., gt=0.0)
    note: str | None = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class TransferInitiateResponse(BaseModel):
    transfer_id: str
    status: str
    fraud_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    action: Literal["APPROVE", "TRIGGER_MFA", "BLOCK"] | None = None
    message: str
    mfa_required: bool = False
    force_logout: bool = False
    sender_balance: float | None = None
    receiver_balance: float | None = None
    request_id: str


class TransferMfaChallengeResponse(BaseModel):
    transfer_id: str
    status: str
    mfa_required: bool
    message: str
    expires_at: datetime
    remaining_attempts: int
    request_id: str
    demo_code: str | None = None


class TransferMfaVerifyRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=10)

    model_config = ConfigDict(extra="forbid")


class DemoSeedResponse(BaseModel):
    seeded: bool
    message: str
    sender_account_number: str
    bank_code: str
    sender_balance: float
    transfers_seeded: int
    completed_transfers: int
    pending_mfa_transfers: int
    blocked_transfers: int


class AdminUnblockUserRequest(BaseModel):
    user_id: str | None = Field(default=None, min_length=8, max_length=128)
    email: str | None = Field(default=None, min_length=3, max_length=320)

    model_config = ConfigDict(extra="forbid")


class AdminUnblockUserResponse(BaseModel):
    user_id: str
    email: str | None = None
    account_id: str
    account_number: str
    bank_code: str
    user_status: str
    account_active: bool
    message: str


def _parse_cors_origins(raw_origins: str | None) -> list[str]:
    if not raw_origins:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
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


def _score_model(
    *,
    payload: TransactionFeatures,
    feature_names: list[str],
    scaler: object,
    model: object,
    thresholds: RiskThresholds,
) -> tuple[float, object, dict]:
    feature_array, raw_input = _prepare_feature_array(payload, feature_names)
    scaled_features = scaler.transform(feature_array)
    probabilities = model.predict_proba(scaled_features)

    if probabilities.shape[1] < 2:
        raise RuntimeError("Model probability output format is invalid.")

    fraud_probability = float(probabilities[0][1])
    decision = evaluate_risk(fraud_probability, thresholds)
    return fraud_probability, decision, raw_input


def _map_transfer_history_item(account_id: str, transfer_row: dict) -> TransferHistoryItem:
    is_outgoing = transfer_row.get("sender_account_id") == account_id
    direction: Literal["INCOMING", "OUTGOING"] = "OUTGOING" if is_outgoing else "INCOMING"
    counterparty_account_number = (
        transfer_row.get("receiver_account_number")
        if is_outgoing
        else transfer_row.get("sender_account_number")
    )
    counterparty_bank_code = (
        transfer_row.get("receiver_bank_code")
        if is_outgoing
        else transfer_row.get("sender_bank_code")
    )

    return TransferHistoryItem(
        transfer_id=str(transfer_row["id"]),
        direction=direction,
        counterparty_account_number=str(counterparty_account_number),
        counterparty_bank_code=str(counterparty_bank_code),
        amount=float(transfer_row["amount"]),
        status=str(transfer_row["status"]),
        risk_level=transfer_row.get("risk_level"),
        action=transfer_row.get("action"),
        note=transfer_row.get("note"),
        created_at=transfer_row["created_at"],
    )


def _assert_account_active(account: dict[str, object]) -> None:
    if not bool(account.get("is_active", False)):
        raise HTTPException(status_code=403, detail="Account is blocked. Contact support.")


def _assert_transfer_owned_by_sender(transfer: dict[str, object], sender_user_id: str) -> None:
    transfer_sender = str(transfer.get("sender_user_id", ""))
    if transfer_sender != sender_user_id:
        raise HTTPException(status_code=404, detail="Transfer request was not found.")


def _load_risk_thresholds() -> RiskThresholds:
    raw_low = os.getenv("LOW_THRESHOLD", str(DEFAULT_LOW_THRESHOLD)).strip()
    raw_high = os.getenv("HIGH_THRESHOLD", str(DEFAULT_HIGH_THRESHOLD)).strip()
    try:
        low = float(raw_low)
        high = float(raw_high)
    except ValueError as exc:
        raise ValueError("LOW_THRESHOLD and HIGH_THRESHOLD must be numeric values.") from exc

    return RiskThresholds(low=low, high=high)


def _parse_bool_env(raw_value: str | None, default: bool, variable_name: str) -> bool:
    if raw_value is None or not raw_value.strip():
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{variable_name} must be a boolean value (true/false).")


def _load_rate_limit_settings() -> RateLimitSettings:
    enabled = _parse_bool_env(
        os.getenv("RATE_LIMIT_ENABLED"),
        DEFAULT_RATE_LIMIT_ENABLED,
        "RATE_LIMIT_ENABLED",
    )
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


def _load_demo_seed_enabled() -> bool:
    return _parse_bool_env(
        os.getenv("ENABLE_DEMO_SEEDING"),
        DEFAULT_ENABLE_DEMO_SEEDING,
        "ENABLE_DEMO_SEEDING",
    )


def _load_mfa_settings() -> MfaSettings:
    raw_ttl = os.getenv("MFA_CODE_TTL_SECONDS", str(DEFAULT_MFA_CODE_TTL_SECONDS)).strip()
    raw_max_attempts = os.getenv("MFA_MAX_ATTEMPTS", str(DEFAULT_MFA_MAX_ATTEMPTS)).strip()
    raw_code_length = os.getenv("MFA_CODE_LENGTH", str(DEFAULT_MFA_CODE_LENGTH)).strip()
    raw_demo_code = os.getenv("ENABLE_DEMO_MFA_CODE_IN_RESPONSE")
    signing_secret = os.getenv("MFA_SIGNING_SECRET", DEFAULT_MFA_SIGNING_SECRET).strip()

    try:
        code_ttl_seconds = int(raw_ttl)
        max_attempts = int(raw_max_attempts)
        code_length = int(raw_code_length)
    except ValueError as exc:
        raise ValueError(
            "MFA_CODE_TTL_SECONDS, MFA_MAX_ATTEMPTS, and MFA_CODE_LENGTH must be integer values."
        ) from exc

    if code_ttl_seconds <= 0:
        raise ValueError("MFA_CODE_TTL_SECONDS must be greater than 0.")
    if max_attempts <= 0:
        raise ValueError("MFA_MAX_ATTEMPTS must be greater than 0.")
    if not 4 <= code_length <= 10:
        raise ValueError("MFA_CODE_LENGTH must be between 4 and 10.")
    if not signing_secret:
        raise ValueError("MFA_SIGNING_SECRET must not be empty.")

    enable_demo_code = _parse_bool_env(
        raw_demo_code,
        DEFAULT_ENABLE_DEMO_MFA_CODE_IN_RESPONSE,
        "ENABLE_DEMO_MFA_CODE_IN_RESPONSE",
    )
    return MfaSettings(
        code_ttl_seconds=code_ttl_seconds,
        max_attempts=max_attempts,
        code_length=code_length,
        enable_demo_code_in_response=enable_demo_code,
        signing_secret=signing_secret,
    )


def _generate_mfa_code(code_length: int) -> str:
    max_value = 10 ** code_length
    return f"{secrets.randbelow(max_value):0{code_length}d}"


def _hash_mfa_code(*, transfer_id: str, code: str, signing_secret: str) -> str:
    payload = f"{transfer_id}:{code}".encode("utf-8")
    return hmac.new(signing_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _parse_iso_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    raise ValueError("Datetime value is invalid.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_root = Path(__file__).resolve().parent.parent
    models_dir = project_root / "models"
    model_version = os.getenv("MODEL_VERSION", DEFAULT_MODEL_VERSION).strip() or DEFAULT_MODEL_VERSION

    artifacts = load_artifacts(models_dir=models_dir)
    repository = SupabaseTransactionRepository(config=SupabaseConfig.from_env())
    auth_settings = load_auth_settings()
    admin_auth_settings: AdminAuthSettings = load_admin_auth_settings()
    user_token_verifier = SupabaseUserTokenVerifier(repository.client)
    banking_repo = BankingRepository(
        client=repository.client,
        config=BankingConfig.from_env(),
    )
    risk_thresholds = _load_risk_thresholds()
    rate_limit_settings = _load_rate_limit_settings()
    rate_limiter = InMemoryRateLimiter(settings=rate_limit_settings)
    enable_demo_seeding = _load_demo_seed_enabled()
    mfa_settings = _load_mfa_settings()

    app.state.model = artifacts.model
    app.state.scaler = artifacts.scaler
    app.state.feature_names = artifacts.feature_names
    app.state.model_version = model_version
    app.state.transaction_repo = repository
    app.state.banking_repo = banking_repo
    app.state.auth_settings = auth_settings
    app.state.admin_auth_settings = admin_auth_settings
    app.state.user_token_verifier = user_token_verifier
    app.state.risk_thresholds = risk_thresholds
    app.state.rate_limit_settings = rate_limit_settings
    app.state.rate_limiter = rate_limiter
    app.state.enable_demo_seeding = enable_demo_seeding
    app.state.mfa_settings = mfa_settings

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
    auth_context: AuthContext = Depends(authenticate_prediction_request),
    __: None = Depends(enforce_prediction_rate_limit),
) -> PredictionResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        fraud_probability, decision, raw_input = _score_model(
            payload=payload,
            feature_names=app.state.feature_names,
            scaler=app.state.scaler,
            model=app.state.model,
            thresholds=app.state.risk_thresholds,
        )

        db_record = {
            **raw_input,
            "fraud_probability": fraud_probability,
            "risk_level": decision.risk_level,
            "action": decision.action,
        }
        app.state.transaction_repo.insert_transaction(db_record)
        logger.info(
            "prediction_scored request_id=%s auth_method=%s principal=%s fraud_probability=%.6f risk_level=%s action=%s",
            request_id,
            auth_context.auth_method,
            auth_context.principal,
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


@app.get("/banking/dashboard", response_model=DashboardResponse)
def get_banking_dashboard(auth_context: AuthContext = Depends(authenticate_banking_user)) -> DashboardResponse:
    try:
        account_bundle = app.state.banking_repo.get_or_create_user_account(
            user_id=auth_context.principal,
            email=auth_context.email,
        )
        account = account_bundle["account"]
        _assert_account_active(account)

        transfers = app.state.banking_repo.list_account_transfers(
            account_id=str(account["id"]),
            limit=DEFAULT_TRANSFER_HISTORY_LIMIT,
            offset=0,
        )
        history = [_map_transfer_history_item(str(account["id"]), transfer) for transfer in transfers]

        return DashboardResponse(
            account=AccountSummary(
                account_id=str(account["id"]),
                account_number=str(account["account_number"]),
                bank_code=str(account["bank_code"]),
                currency=str(account["currency"]),
                balance=float(account["balance"]),
                is_active=bool(account["is_active"]),
            ),
            recent_transactions=history,
        )
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/banking/transactions", response_model=TransactionHistoryResponse)
def get_banking_transactions(
    auth_context: AuthContext = Depends(authenticate_banking_user),
    limit: int = Query(DEFAULT_TRANSFER_HISTORY_LIMIT, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TransactionHistoryResponse:
    try:
        account_bundle = app.state.banking_repo.get_or_create_user_account(
            user_id=auth_context.principal,
            email=auth_context.email,
        )
        account = account_bundle["account"]
        _assert_account_active(account)

        transfers = app.state.banking_repo.list_account_transfers(
            account_id=str(account["id"]),
            limit=limit,
            offset=offset,
        )
        return TransactionHistoryResponse(
            items=[_map_transfer_history_item(str(account["id"]), transfer) for transfer in transfers],
            limit=limit,
            offset=offset,
        )
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/banking/demo/seed", response_model=DemoSeedResponse)
def seed_banking_demo_data(auth_context: AuthContext = Depends(authenticate_banking_user)) -> DemoSeedResponse:
    demo_seed_enabled = bool(getattr(app.state, "enable_demo_seeding", False))
    if not demo_seed_enabled:
        raise HTTPException(
            status_code=403,
            detail="Demo seeding endpoint is disabled. Set ENABLE_DEMO_SEEDING=true to enable it.",
        )

    try:
        seed_result = app.state.banking_repo.seed_demo_data_for_user(
            user_id=auth_context.principal,
            email=auth_context.email,
        )

        sender_account_number = seed_result.get("sender_account_number")
        bank_code = seed_result.get("bank_code")
        sender_balance = seed_result.get("sender_balance")

        if sender_account_number is None or bank_code is None or sender_balance is None:
            account_bundle = app.state.banking_repo.get_or_create_user_account(
                user_id=auth_context.principal,
                email=auth_context.email,
            )
            account = account_bundle["account"]
            sender_account_number = sender_account_number or account["account_number"]
            bank_code = bank_code or account["bank_code"]
            sender_balance = float(sender_balance if sender_balance is not None else account["balance"])

        return DemoSeedResponse(
            seeded=bool(seed_result.get("seeded", True)),
            message=str(seed_result.get("message", "Demo banking data seeded.")),
            sender_account_number=str(sender_account_number),
            bank_code=str(bank_code),
            sender_balance=float(sender_balance),
            transfers_seeded=int(seed_result.get("transfers_seeded", 0)),
            completed_transfers=int(seed_result.get("completed_transfers", 0)),
            pending_mfa_transfers=int(seed_result.get("pending_mfa_transfers", 0)),
            blocked_transfers=int(seed_result.get("blocked_transfers", 0)),
        )
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/banking/admin/unblock-user", response_model=AdminUnblockUserResponse)
def admin_unblock_user(
    payload: AdminUnblockUserRequest,
    _: AuthContext = Depends(authenticate_banking_admin_request),
) -> AdminUnblockUserResponse:
    normalized_user_id = payload.user_id.strip() if payload.user_id else ""
    normalized_email = payload.email.strip() if payload.email else ""

    if not normalized_user_id and not normalized_email:
        raise HTTPException(status_code=400, detail="Provide either user_id or email.")

    try:
        target_profile: dict[str, object] | None = None
        if normalized_user_id:
            target_profile = app.state.banking_repo.get_user_profile(normalized_user_id)
        elif normalized_email:
            target_profile = app.state.banking_repo.get_user_profile_by_email(normalized_email)

        if not target_profile:
            raise HTTPException(status_code=404, detail="Target user was not found.")

        unblocked = app.state.banking_repo.unblock_user_and_account(user_id=str(target_profile["id"]))
        profile = unblocked["profile"]
        account = unblocked["account"]
        return AdminUnblockUserResponse(
            user_id=str(profile["id"]),
            email=profile.get("email"),
            account_id=str(account["id"]),
            account_number=str(account["account_number"]),
            bank_code=str(account["bank_code"]),
            user_status=str(profile.get("status", "UNKNOWN")),
            account_active=bool(account.get("is_active", False)),
            message="User account reactivated successfully.",
        )
    except HTTPException:
        raise
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/banking/validate-receiver", response_model=ReceiverValidationResponse)
def validate_receiver_account(
    payload: ReceiverValidationRequest,
    auth_context: AuthContext = Depends(authenticate_banking_user),
) -> ReceiverValidationResponse:
    try:
        account_bundle = app.state.banking_repo.get_or_create_user_account(
            user_id=auth_context.principal,
            email=auth_context.email,
        )
        sender_account = account_bundle["account"]
        _assert_account_active(sender_account)

        receiver_account = app.state.banking_repo.get_account_by_bank_details(
            bank_code=payload.receiver_bank_code,
            account_number=payload.receiver_account_number,
        )
        if not receiver_account:
            return ReceiverValidationResponse(
                exists=False,
                message="Receiver account was not found.",
            )

        if str(receiver_account["id"]) == str(sender_account["id"]):
            return ReceiverValidationResponse(
                exists=False,
                message="Sender and receiver account cannot be the same.",
            )

        if not bool(receiver_account.get("is_active", False)):
            return ReceiverValidationResponse(
                exists=False,
                message="Receiver account is currently inactive.",
            )

        receiver_profile = app.state.banking_repo.get_user_profile(str(receiver_account["user_id"]))
        account_holder = (
            receiver_profile.get("full_name")
            if receiver_profile and receiver_profile.get("full_name")
            else receiver_profile.get("email") if receiver_profile else None
        )

        return ReceiverValidationResponse(
            exists=True,
            account_holder=str(account_holder) if account_holder else None,
            account_number_masked=mask_account_number(str(receiver_account["account_number"])),
            bank_code=str(receiver_account["bank_code"]),
            message="Receiver account validated.",
        )
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/banking/transfers/initiate", response_model=TransferInitiateResponse)
def initiate_banking_transfer(
    request: Request,
    payload: InitiateTransferRequest,
    auth_context: AuthContext = Depends(authenticate_banking_user),
    __: None = Depends(enforce_prediction_rate_limit),
) -> TransferInitiateResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        account_bundle = app.state.banking_repo.get_or_create_user_account(
            user_id=auth_context.principal,
            email=auth_context.email,
        )
        sender_account = account_bundle["account"]
        sender_profile = account_bundle["profile"]
        _assert_account_active(sender_account)

        receiver_account = app.state.banking_repo.get_account_by_bank_details(
            bank_code=payload.receiver_bank_code,
            account_number=payload.receiver_account_number,
        )
        if not receiver_account:
            raise HTTPException(status_code=404, detail="Receiver account was not found.")
        if not bool(receiver_account.get("is_active", False)):
            raise HTTPException(status_code=400, detail="Receiver account is inactive.")
        if str(receiver_account["id"]) == str(sender_account["id"]):
            raise HTTPException(status_code=400, detail="Sender and receiver account cannot be the same.")

        feature_context = compute_transfer_feature_context(
            amount=payload.amount,
            sender_old_balance=float(sender_account["balance"]),
            receiver_old_balance=float(receiver_account["balance"]),
        )
        feature_payload = build_model_feature_payload(feature_context)
        transaction_features = TransactionFeatures(**feature_payload)
        fraud_probability, decision, raw_input = _score_model(
            payload=transaction_features,
            feature_names=app.state.feature_names,
            scaler=app.state.scaler,
            model=app.state.model,
            thresholds=app.state.risk_thresholds,
        )

        if decision.action == "APPROVE":
            status = "COMPLETED_PENDING_POSTING"
        elif decision.action == "TRIGGER_MFA":
            status = "MFA_REQUIRED"
        else:
            status = "REJECTED_HIGH_RISK"

        transfer_row = app.state.banking_repo.create_transfer_request(
            {
                "sender_account_id": sender_account["id"],
                "receiver_account_id": receiver_account["id"],
                "sender_account_number": sender_account["account_number"],
                "sender_bank_code": sender_account["bank_code"],
                "receiver_account_number": receiver_account["account_number"],
                "receiver_bank_code": receiver_account["bank_code"],
                "sender_user_id": sender_profile["id"],
                "receiver_user_id": receiver_account["user_id"],
                "amount": payload.amount,
                "note": payload.note,
                "status": status,
                "risk_level": decision.risk_level,
                "action": decision.action,
                "fraud_probability": fraud_probability,
                "model_version": app.state.model_version,
                "request_id": request_id,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

        app.state.transaction_repo.insert_transaction(
            {
                **raw_input,
                "fraud_probability": fraud_probability,
                "risk_level": decision.risk_level,
                "action": decision.action,
            }
        )

        if decision.action == "APPROVE":
            posting = app.state.banking_repo.execute_low_risk_transfer(
                transfer_request_id=str(transfer_row["id"]),
                sender_account_id=str(sender_account["id"]),
                receiver_account_id=str(receiver_account["id"]),
                amount=payload.amount,
                note=payload.note,
            )
            return TransferInitiateResponse(
                transfer_id=str(transfer_row["id"]),
                status="COMPLETED",
                fraud_probability=fraud_probability,
                risk_level=decision.risk_level,
                action=decision.action,
                message="Transfer approved and posted successfully.",
                mfa_required=False,
                force_logout=False,
                sender_balance=float(posting["sender_balance_after"]),
                receiver_balance=float(posting["receiver_balance_after"]),
                request_id=request_id,
            )

        if decision.action == "TRIGGER_MFA":
            return TransferInitiateResponse(
                transfer_id=str(transfer_row["id"]),
                status="MFA_REQUIRED",
                fraud_probability=fraud_probability,
                risk_level=decision.risk_level,
                action=decision.action,
                message="Transfer flagged for additional verification. Complete MFA to continue.",
                mfa_required=True,
                force_logout=False,
                sender_balance=float(sender_account["balance"]),
                receiver_balance=float(receiver_account["balance"]),
                request_id=request_id,
            )

        app.state.banking_repo.block_user_and_account(
            user_id=str(sender_profile["id"]),
            account_id=str(sender_account["id"]),
        )
        return TransferInitiateResponse(
            transfer_id=str(transfer_row["id"]),
            status="REJECTED_HIGH_RISK",
            fraud_probability=fraud_probability,
            risk_level=decision.risk_level,
            action=decision.action,
            message="High-risk transfer detected. Account blocked and session must be terminated.",
            mfa_required=False,
            force_logout=True,
            sender_balance=None,
            receiver_balance=None,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except DatabaseError as exc:
        logger.error("banking_transfer_db_error request_id=%s error=%s", request_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("banking_transfer_validation_error request_id=%s error=%s", request_id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("banking_transfer_internal_error request_id=%s", request_id)
        raise HTTPException(status_code=500, detail="Internal server error during transfer initiation.") from exc


@app.post("/banking/transfers/{transfer_id}/mfa/challenge", response_model=TransferMfaChallengeResponse)
def create_transfer_mfa_challenge(
    transfer_id: str,
    request: Request,
    auth_context: AuthContext = Depends(authenticate_banking_user),
    __: None = Depends(enforce_prediction_rate_limit),
) -> TransferMfaChallengeResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        account_bundle = app.state.banking_repo.get_or_create_user_account(
            user_id=auth_context.principal,
            email=auth_context.email,
        )
        sender_account = account_bundle["account"]
        _assert_account_active(sender_account)

        transfer = app.state.banking_repo.get_transfer_request_by_id(transfer_id)
        if not transfer:
            raise HTTPException(status_code=404, detail="Transfer request was not found.")
        _assert_transfer_owned_by_sender(transfer, auth_context.principal)

        if str(transfer.get("status")) != "MFA_REQUIRED":
            raise HTTPException(
                status_code=400,
                detail=f"Transfer is not eligible for MFA challenge in current status '{transfer.get('status')}'.",
            )

        mfa_settings: MfaSettings = app.state.mfa_settings
        code = _generate_mfa_code(mfa_settings.code_length)
        expires_at = datetime.now(UTC) + timedelta(seconds=mfa_settings.code_ttl_seconds)
        challenge_payload = {
            "transfer_request_id": transfer_id,
            "sender_user_id": auth_context.principal,
            "code_hash": _hash_mfa_code(
                transfer_id=transfer_id,
                code=code,
                signing_secret=mfa_settings.signing_secret,
            ),
            "code_length": mfa_settings.code_length,
            "attempts": 0,
            "max_attempts": mfa_settings.max_attempts,
            "status": "PENDING",
            "expires_at": expires_at.isoformat(),
            "verified_at": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        app.state.banking_repo.upsert_transfer_mfa_challenge(challenge_payload)

        return TransferMfaChallengeResponse(
            transfer_id=transfer_id,
            status="MFA_REQUIRED",
            mfa_required=True,
            message="MFA challenge generated. Verify the code to complete transfer posting.",
            expires_at=expires_at,
            remaining_attempts=mfa_settings.max_attempts,
            request_id=request_id,
            demo_code=code if mfa_settings.enable_demo_code_in_response else None,
        )
    except HTTPException:
        raise
    except DatabaseError as exc:
        logger.error("mfa_challenge_db_error request_id=%s error=%s", request_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("mfa_challenge_internal_error request_id=%s", request_id)
        raise HTTPException(status_code=500, detail="Internal server error during MFA challenge creation.") from exc


@app.post("/banking/transfers/{transfer_id}/mfa/verify", response_model=TransferInitiateResponse)
def verify_transfer_mfa_and_post(
    transfer_id: str,
    payload: TransferMfaVerifyRequest,
    request: Request,
    auth_context: AuthContext = Depends(authenticate_banking_user),
    __: None = Depends(enforce_prediction_rate_limit),
) -> TransferInitiateResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        account_bundle = app.state.banking_repo.get_or_create_user_account(
            user_id=auth_context.principal,
            email=auth_context.email,
        )
        sender_account = account_bundle["account"]
        _assert_account_active(sender_account)

        transfer = app.state.banking_repo.get_transfer_request_by_id(transfer_id)
        if not transfer:
            raise HTTPException(status_code=404, detail="Transfer request was not found.")
        _assert_transfer_owned_by_sender(transfer, auth_context.principal)

        transfer_status = str(transfer.get("status"))
        if transfer_status != "MFA_REQUIRED":
            raise HTTPException(
                status_code=400,
                detail=f"Transfer is not awaiting MFA verification in current status '{transfer_status}'.",
            )

        challenge = app.state.banking_repo.get_transfer_mfa_challenge(transfer_id)
        if not challenge:
            raise HTTPException(status_code=400, detail="MFA challenge was not initiated for this transfer.")

        challenge_status = str(challenge.get("status", "PENDING"))
        max_attempts = int(challenge.get("max_attempts") or app.state.mfa_settings.max_attempts)
        attempts = int(challenge.get("attempts") or 0)

        if challenge_status == "LOCKED":
            raise HTTPException(
                status_code=403,
                detail="MFA challenge is locked due to failed attempts. Request a new challenge.",
            )
        if challenge_status == "VERIFIED":
            raise HTTPException(status_code=409, detail="MFA challenge was already verified.")

        expires_at = _parse_iso_datetime(challenge.get("expires_at"))
        now_utc = datetime.now(UTC)
        if expires_at <= now_utc:
            app.state.banking_repo.update_transfer_mfa_challenge(
                transfer_request_id=transfer_id,
                updates={"status": "EXPIRED"},
            )
            raise HTTPException(status_code=401, detail="MFA code expired. Request a new challenge.")

        expected_hash = _hash_mfa_code(
            transfer_id=transfer_id,
            code=payload.code.strip(),
            signing_secret=app.state.mfa_settings.signing_secret,
        )
        stored_hash = str(challenge.get("code_hash", ""))
        if not hmac.compare_digest(expected_hash, stored_hash):
            attempts += 1
            challenge_updates: dict[str, object] = {"attempts": attempts}
            if attempts >= max_attempts:
                challenge_updates["status"] = "LOCKED"
            app.state.banking_repo.update_transfer_mfa_challenge(
                transfer_request_id=transfer_id,
                updates=challenge_updates,
            )

            remaining_attempts = max(max_attempts - attempts, 0)
            if remaining_attempts <= 0:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid MFA code. Challenge locked. Request a new challenge.",
                )
            raise HTTPException(
                status_code=401,
                detail=f"Invalid MFA code. {remaining_attempts} attempt(s) remaining.",
            )

        app.state.banking_repo.update_transfer_mfa_challenge(
            transfer_request_id=transfer_id,
            updates={"status": "VERIFIED", "verified_at": now_utc.isoformat()},
        )
        app.state.banking_repo.update_transfer_request_status(
            transfer_request_id=transfer_id,
            status="COMPLETED_PENDING_POSTING",
        )

        posting = app.state.banking_repo.execute_low_risk_transfer(
            transfer_request_id=transfer_id,
            sender_account_id=str(transfer["sender_account_id"]),
            receiver_account_id=str(transfer["receiver_account_id"]),
            amount=float(transfer["amount"]),
            note=transfer.get("note"),
        )

        fraud_probability = transfer.get("fraud_probability")
        return TransferInitiateResponse(
            transfer_id=transfer_id,
            status="COMPLETED",
            fraud_probability=float(fraud_probability) if fraud_probability is not None else None,
            risk_level=transfer.get("risk_level"),
            action=transfer.get("action"),
            message="MFA verified. Transfer posted successfully.",
            mfa_required=False,
            force_logout=False,
            sender_balance=float(posting["sender_balance_after"]),
            receiver_balance=float(posting["receiver_balance_after"]),
            request_id=request_id,
        )
    except HTTPException:
        raise
    except DatabaseError as exc:
        logger.error("mfa_verify_db_error request_id=%s error=%s", request_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("mfa_verify_validation_error request_id=%s error=%s", request_id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("mfa_verify_internal_error request_id=%s", request_id)
        raise HTTPException(status_code=500, detail="Internal server error during MFA verification.") from exc
