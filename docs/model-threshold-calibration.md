# Model Threshold Calibration Report

Date: 2026-02-14  
Model: `models/random_forest_model.joblib` (`RandomForestClassifier`, 100 trees)  
Data: `cleaned_dataset/cleaned_fraud_detection_file.csv` (2,684,404 rows)

Note:
- This is a baseline threshold analysis on the uncalibrated artifact.

## Scope

This report evaluates threshold behavior for the 3-level risk engine.

Important:
- The banking transfer API always scores transfer transactions (`type_TRANSFER=true`).
- Therefore, threshold calibration for production decisions should use the transfer subset, not all transaction types.

## Dataset Summary

All rows:
- Rows: `2,684,404`
- Fraud rows: `4,097`
- Fraud rate: `0.1526%`

Transfer-only rows (`type_TRANSFER=1`):
- Rows: `532,909`
- Fraud rows: `4,097`
- Fraud rate: `0.7688%`

## Probability Distribution (Transfer-Only)

- `p == 0.0`: `98.5598%` of transfer rows
- `p <= 0.01`: `99.0162%`
- `p >= 0.70`: `0.7656%`
- Quantiles:
  - `p50 = 0.0`
  - `p90 = 0.0`
  - `p95 = 0.0`
  - `p99 = 0.01`
  - `p99.5 ~= 0.9997`
  - `p99.9 = 1.0`

Implication:
- Scores are extremely bimodal/discrete for transfer rows.
- A “balanced” LOW/MEDIUM/HIGH volume split cannot be achieved by threshold tuning alone with current model outputs.

## Current/Alternative Threshold Policies (Transfer-Only)

### Policy A: `LOW<0.30`, `HIGH>=0.70` (original)

- LOW:
  - Count: `528,809` (`99.2306%`)
  - Fraud rate: `0.000378%` (2 frauds)
- MEDIUM:
  - Count: `20` (`0.003753%`)
  - Fraud rate: `75.0%` (15 frauds)
- HIGH:
  - Count: `4,080` (`0.7656%`)
  - Fraud rate: `100%` (4,080 frauds)

### Policy B: `LOW<0.30`, `HIGH>=0.45` (your current test setting)

- LOW:
  - Count: `528,809` (`99.2306%`)
  - Fraud rate: `0.000378%` (2 frauds)
- MEDIUM:
  - Count: `2` (`0.000375%`)
  - Fraud rate: `0%` (0 frauds)
- HIGH:
  - Count: `4,098` (`0.7690%`)
  - Fraud rate: `99.9268%` (4,095 frauds)

### Policy C: `LOW<0.01`, `HIGH>=0.05` (more medium volume, still small)

- LOW:
  - Count: `527,138` (`98.9171%`)
  - Fraud rate: `0.000379%` (2 frauds)
- MEDIUM:
  - Count: `1,598` (`0.2999%`)
  - Fraud rate: `0%` (0 frauds)
- HIGH:
  - Count: `4,173` (`0.7831%`)
  - Fraud rate: `98.1308%` (4,095 frauds)

## Alert Threshold Precision/Recall (Transfer-Only)

Treating “alert” as `probability >= threshold`:

- `t=0.30`: precision `99.8780%`, recall `99.9512%`
- `t=0.45`: precision `99.9268%`, recall `99.9512%`
- `t=0.70`: precision `100%`, recall `99.5851%`

## Time-of-Day Impact (Transfer-Only)

Average predicted fraud probability by hour (selected):
- Hour 05: `0.7037`
- Hour 04: `0.5808`
- Hour 03: `0.4670`
- Hour 02: `0.2785`
- Hour 12: `0.0041`
- Hour 19: `0.0034`

Interpretation:
- Time-of-day meaningfully influences risk distribution in transfer traffic.
- Still, timestamp should remain server-derived to prevent client tampering.

## Recommendation

For production with current model:
- Keep thresholds close to strict settings:
  - Option 1 (safer precision): `LOW=0.30`, `HIGH=0.70`
  - Option 2 (slightly more catch, tiny precision cost): `LOW=0.30`, `HIGH=0.45`
- Do not expect medium bucket to carry significant volume with current model outputs.

To get a genuinely useful medium bucket:
- Add score calibration (Platt/Isotonic), and/or
- Retrain with objective/features that reduce score collapse at 0/1 for transfer rows.
