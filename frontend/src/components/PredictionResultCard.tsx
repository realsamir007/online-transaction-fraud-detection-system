import type { PredictionResult } from "../types";

type Props = {
  result: PredictionResult | null;
  error: string;
  isLoading: boolean;
};

function riskClassName(riskLevel: PredictionResult["risk_level"]) {
  if (riskLevel === "HIGH") {
    return "risk risk-high";
  }
  if (riskLevel === "MEDIUM") {
    return "risk risk-medium";
  }
  return "risk risk-low";
}

export default function PredictionResultCard({ result, error, isLoading }: Props) {
  return (
    <section className="panel panel-result">
      <div className="panel-header">
        <h2>Decision Output</h2>
        <p>Real-time model inference and risk action.</p>
      </div>

      {isLoading && <p className="muted">Scoring transaction...</p>}
      {error && !isLoading && <p className="error">{error}</p>}

      {!isLoading && !error && !result && (
        <p className="muted">Submit a transaction to view fraud probability and action.</p>
      )}

      {result && !isLoading && !error && (
        <div className="result-stack">
          <div className={riskClassName(result.risk_level)}>
            <span>{result.risk_level}</span>
            <strong>{result.action}</strong>
          </div>
          <dl>
            <div>
              <dt>Fraud Probability</dt>
              <dd>{(result.fraud_probability * 100).toFixed(2)}%</dd>
            </div>
            <div>
              <dt>Message</dt>
              <dd>{result.message}</dd>
            </div>
            <div>
              <dt>Model Version</dt>
              <dd>{result.model_version}</dd>
            </div>
            <div>
              <dt>Request ID</dt>
              <dd>{result.requestId}</dd>
            </div>
          </dl>
        </div>
      )}
    </section>
  );
}

