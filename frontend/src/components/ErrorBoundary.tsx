import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}
interface State {
  error: Error | null;
}

/** Catches render-time crashes so one broken view doesn't blank the whole app. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("UI crashed", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div role="alert" className="card error-card">
            <h2>Something went wrong on this page.</h2>
            <p>The rest of CivicPulse still works. Try reloading, or use the navigation above.</p>
            <button onClick={() => this.setState({ error: null })}>Try again</button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
