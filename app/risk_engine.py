from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:
    risk_level: str
    action: str
    message: str


@dataclass(frozen=True)
class RiskThresholds:
    low: float = 0.30
    high: float = 0.70

    def __post_init__(self) -> None:
        if not 0.0 <= self.low <= 1.0:
            raise ValueError("LOW_THRESHOLD must be between 0 and 1.")
        if not 0.0 <= self.high <= 1.0:
            raise ValueError("HIGH_THRESHOLD must be between 0 and 1.")
        if self.low >= self.high:
            raise ValueError("LOW_THRESHOLD must be less than HIGH_THRESHOLD.")


def evaluate_risk(probability: float, thresholds: RiskThresholds) -> RiskDecision:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("Fraud probability must be between 0 and 1.")

    if probability < thresholds.low:
        return RiskDecision(
            risk_level="LOW",
            action="APPROVE",
            message="Transaction approved",
        )

    if probability < thresholds.high:
        return RiskDecision(
            risk_level="MEDIUM",
            action="TRIGGER_MFA",
            message="Transaction flagged for multi-factor authentication",
        )

    return RiskDecision(
        risk_level="HIGH",
        action="BLOCK",
        message="Transaction blocked due to high fraud risk",
    )
