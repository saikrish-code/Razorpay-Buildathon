import { Component, type ErrorInfo, type ReactNode } from "react";
import "./ErrorBoundary.css";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  showDetails: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    showDetails: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, showDetails: false };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error caught by ErrorBoundary:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null, showDetails: false });
  };

  private handleReload = () => {
    window.location.reload();
  };

  private toggleDetails = () => {
    this.setState((prev) => ({ showDetails: !prev.showDetails }));
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="error-boundary-fallback" role="alert">
          <div className="error-boundary-card">
            <div className="error-boundary-icon-wrapper">
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>

            <h2 className="error-boundary-title">
              Something went wrong loading this page — check the API connection
            </h2>

            <p className="error-boundary-message">
              An unexpected error occurred during rendering or data retrieval. The API
              backend may be temporarily unavailable or returned invalid data.
            </p>

            <div className="error-boundary-actions">
              <button
                type="button"
                className="error-boundary-btn error-boundary-btn-primary"
                onClick={this.handleReload}
                id="error-boundary-reload-btn"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
                <span>Reload page</span>
              </button>

              <button
                type="button"
                className="error-boundary-btn error-boundary-btn-secondary"
                onClick={this.handleReset}
                id="error-boundary-retry-btn"
              >
                <span>Try again</span>
              </button>
            </div>

            {this.state.error && (
              <div>
                <button
                  type="button"
                  className="error-boundary-details-toggle"
                  onClick={this.toggleDetails}
                >
                  {this.state.showDetails ? "Hide error details" : "Show error details"}
                </button>

                {this.state.showDetails && (
                  <pre className="error-boundary-details">
                    {this.state.error.name}: {this.state.error.message}
                    {this.state.error.stack ? `\n\n${this.state.error.stack}` : ""}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
