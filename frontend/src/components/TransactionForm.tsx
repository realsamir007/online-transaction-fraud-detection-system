import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import type { TransactionPayload } from "../types";

type Props = {
  disabled: boolean;
  onSubmit: (payload: TransactionPayload) => Promise<void>;
};

const initialValues: TransactionPayload = {
  step: 1,
  amount: 1000,
  oldbalanceOrg: 5000,
  newbalanceOrig: 4000,
  oldbalanceDest: 10000,
  newbalanceDest: 11000,
  hour: 2,
  is_night: true,
  amount_ratio: 0.2,
  sender_balance_change: -1000,
  receiver_balance_change: 1000,
  orig_balance_zero: false,
  dest_balance_zero: false,
  type_TRANSFER: true,
};

export default function TransactionForm({ disabled, onSubmit }: Props) {
  const [values, setValues] = useState<TransactionPayload>(initialValues);

  const fields = useMemo(
    () => [
      { key: "step", label: "Step", min: 0, step: "1" },
      { key: "amount", label: "Amount", min: 0, step: "0.01" },
      { key: "oldbalanceOrg", label: "Old Sender Balance", min: 0, step: "0.01" },
      { key: "newbalanceOrig", label: "New Sender Balance", min: 0, step: "0.01" },
      { key: "oldbalanceDest", label: "Old Receiver Balance", min: 0, step: "0.01" },
      { key: "newbalanceDest", label: "New Receiver Balance", min: 0, step: "0.01" },
      { key: "hour", label: "Hour (0-23)", min: 0, max: 23, step: "1" },
      { key: "amount_ratio", label: "Amount Ratio", min: 0, step: "0.000001" },
      { key: "sender_balance_change", label: "Sender Balance Change", step: "0.01" },
      { key: "receiver_balance_change", label: "Receiver Balance Change", step: "0.01" },
    ] as const,
    [],
  );

  function updateNumberField(key: keyof TransactionPayload, rawValue: string) {
    const parsedValue = rawValue === "" ? 0 : Number(rawValue);
    setValues((previous) => ({ ...previous, [key]: parsedValue }));
  }

  function updateBooleanField(key: keyof TransactionPayload, checked: boolean) {
    setValues((previous) => ({ ...previous, [key]: checked }));
  }

  async function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(values);
  }

  return (
    <form className="panel panel-form" onSubmit={submitForm}>
      <div className="panel-header">
        <h2>Transaction Features</h2>
        <p>Provide all model features in one request.</p>
      </div>

      <div className="grid">
        {fields.map((field) => (
          <label key={field.key} className="field">
            <span>{field.label}</span>
            <input
              type="number"
              value={String(values[field.key] ?? "")}
              min={field.min}
              max={field.max}
              step={field.step}
              onChange={(event) => updateNumberField(field.key, event.target.value)}
              required
              disabled={disabled}
            />
          </label>
        ))}
      </div>

      <div className="switches">
        <label>
          <input
            type="checkbox"
            checked={values.is_night}
            onChange={(event) => updateBooleanField("is_night", event.target.checked)}
            disabled={disabled}
          />
          Night Transaction
        </label>
        <label>
          <input
            type="checkbox"
            checked={values.orig_balance_zero}
            onChange={(event) => updateBooleanField("orig_balance_zero", event.target.checked)}
            disabled={disabled}
          />
          Sender Balance Zero
        </label>
        <label>
          <input
            type="checkbox"
            checked={values.dest_balance_zero}
            onChange={(event) => updateBooleanField("dest_balance_zero", event.target.checked)}
            disabled={disabled}
          />
          Receiver Balance Zero
        </label>
        <label>
          <input
            type="checkbox"
            checked={values.type_TRANSFER}
            onChange={(event) => updateBooleanField("type_TRANSFER", event.target.checked)}
            disabled={disabled}
          />
          Transfer Transaction
        </label>
      </div>

      <button type="submit" className="primary-btn" disabled={disabled}>
        {disabled ? "Scoring..." : "Score Transaction"}
      </button>
    </form>
  );
}
