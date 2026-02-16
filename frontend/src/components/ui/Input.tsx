import type { InputHTMLAttributes } from "react";

type Props = {
  label: string;
  error?: string;
  hint?: string;
  containerClassName?: string;
} & InputHTMLAttributes<HTMLInputElement>;

export function Input({ label, error, hint, id, containerClassName, className, ...rest }: Props) {
  const resolvedId = id || label.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const resolvedClassName = ["ui-input", error ? "ui-input-error" : "", className || ""]
    .filter(Boolean)
    .join(" ");

  return (
    <label className={["ui-field", containerClassName || ""].filter(Boolean).join(" ")} htmlFor={resolvedId}>
      <span className="ui-field-label">{label}</span>
      <input id={resolvedId} className={resolvedClassName} {...rest} />
      {error ? <span className="ui-field-error">{error}</span> : null}
      {!error && hint ? <span className="ui-field-hint">{hint}</span> : null}
    </label>
  );
}
