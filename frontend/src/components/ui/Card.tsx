import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
};

export function Card({ children, title, subtitle, actions, className }: Props) {
  return (
    <section className={["ui-card", className || ""].filter(Boolean).join(" ")}>
      {title || subtitle || actions ? (
        <header className="ui-card-header">
          <div>
            {title ? <h3>{title}</h3> : null}
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          {actions ? <div className="ui-card-actions">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}
