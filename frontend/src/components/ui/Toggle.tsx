import type { InputHTMLAttributes } from "react";

type Props = {
  label: string;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "type">;

export function Toggle({ label, checked, onChange, ...rest }: Props) {
  return (
    <label className="ui-toggle">
      <span>{label}</span>
      <span className="ui-toggle-track">
        <input type="checkbox" checked={checked} onChange={onChange} {...rest} />
        <span className="ui-toggle-thumb" />
      </span>
    </label>
  );
}
