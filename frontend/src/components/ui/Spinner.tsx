type SpinnerSize = "sm" | "md" | "lg";

type Props = {
  size?: SpinnerSize;
};

export function Spinner({ size = "md" }: Props) {
  return <span className={`ui-spinner ui-spinner-${size}`} aria-label="Loading" />;
}
