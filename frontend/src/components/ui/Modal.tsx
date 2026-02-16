import { useEffect } from "react";
import type { ReactNode } from "react";

type Props = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
};

export function Modal({ open, title, onClose, children, footer, size = "md" }: Props) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", onKeydown);
    return () => {
      document.removeEventListener("keydown", onKeydown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div className="ui-modal-overlay" role="presentation" onClick={onClose}>
      <div
        className={`ui-modal ui-modal-${size}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="ui-modal-header">
          <h4>{title}</h4>
          <button className="ui-modal-close" type="button" onClick={onClose} aria-label="Close modal">
            x
          </button>
        </header>
        <div className="ui-modal-body">{children}</div>
        {footer ? <footer className="ui-modal-footer">{footer}</footer> : null}
      </div>
    </div>
  );
}
