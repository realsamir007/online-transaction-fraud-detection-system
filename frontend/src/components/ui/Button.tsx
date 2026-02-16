import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Spinner } from "./Spinner";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

type Props = {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  loading?: boolean;
} & ButtonHTMLAttributes<HTMLButtonElement>;

export function Button({
  children,
  variant = "primary",
  size = "md",
  fullWidth = false,
  loading = false,
  className,
  disabled,
  ...rest
}: Props) {
  const resolvedClassName = [
    "ui-button",
    `ui-button-${variant}`,
    `ui-button-${size}`,
    fullWidth ? "ui-button-full" : "",
    className || "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button className={resolvedClassName} disabled={disabled || loading} {...rest}>
      {loading ? (
        <span className="ui-button-loading">
          <Spinner size="sm" />
          <span>Loading...</span>
        </span>
      ) : (
        children
      )}
    </button>
  );
}
