import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

type Props = {
  children: ReactNode;
};

type State = {
  hasError: boolean;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
  };

  static getDerivedStateFromError(): State {
    return {
      hasError: true,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Frontend runtime error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="app-shell app-shell-centered">
          <section className="error-fallback-card">
            <h1>Something went wrong</h1>
            <p>Unexpected UI error occurred. Refresh the page and try again.</p>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
