import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { frontendLoggingService } from '../services/frontendLoggingService';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

/**
 * Error Boundary component to catch and handle runtime errors
 */
export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI
    return {
      hasError: true,
      error,
    };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    frontendLoggingService.error('ErrorBoundary', 'ErrorBoundary caught an error', error, {
      componentStack: errorInfo.componentStack
    });

    this.setState({
      error,
      errorInfo,
    });

    // Call the onError callback if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // You can also log the error to an error reporting service here
    // logErrorToService(error, errorInfo);
  }

  private handleReset = () => {
    this.setState({
      hasError: false,
      error: undefined,
      errorInfo: undefined,
    });
  };

  private handleReload = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      // You can render any custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen bg-base-200 flex items-center justify-center p-4">
          <div className="card bg-base-100 shadow-xl max-w-md w-full shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
            <div className="card-body text-center">
              <div className="flex justify-center mb-4">
                <div className="w-16 h-16 bg-error text-error-content rounded-full flex items-center justify-center">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-8 w-8"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
                    />
                  </svg>
                </div>
              </div>
              
              <h2 className="card-title justify-center text-error mb-2">
                Something went wrong
              </h2>
              
              <p className="text-readout mb-4">
                We encountered an unexpected error. This has been logged and our team has been notified.
              </p>

              {import.meta.env.DEV && this.state.error && (
                <div className="mockup-code text-left mb-4">
                  <pre className="text-xs">
                    <code>{this.state.error.toString()}</code>
                  </pre>
                  {this.state.errorInfo && (
                    <pre className="text-xs mt-2">
                      <code>{this.state.errorInfo.componentStack}</code>
                    </pre>
                  )}
                </div>
              )}

              <div className="card-actions justify-center gap-2">
                <button
                  onClick={this.handleReset}
                  className="btn btn-primary btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                >
                  Try Again
                </button>

                <button
                  onClick={this.handleReload}
                  className="btn btn-outline btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                >
                  Reload Page
                </button>

                <Link to="/" className="btn btn-ghost btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]">
                  Go Home
                </Link>
              </div>

              <div className="mt-4 text-sm text-readout">
                <p>If the problem persists, please contact support.</p>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Specific error boundary for API errors
 */
export class ApiErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    // Only handle API-related errors
    if (error.message.includes('HTTP') || error.message.includes('Network')) {
      return {
        hasError: true,
        error,
      };
    }
    // Re-throw non-API errors
    throw error;
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="alert alert-error shadow-lg">
          <div>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="stroke-current flex-shrink-0 h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <h3 className="font-bold">Connection Error</h3>
              <div className="text-xs">
                Unable to connect to the server. Please check your connection and try again.
              </div>
            </div>
          </div>
          <div className="flex-none">
            <button
              onClick={() => window.location.reload()}
              className="btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] btn-ghost rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
            >
              Retry
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Hook for using error boundaries in functional components
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useErrorHandler() {
  const handleError = (error: Error, context?: string) => {
    frontendLoggingService.error('ErrorHandler', `Error in ${context || 'unknown context'}`, error);

    // You can add error reporting service calls here
    // reportError(error, { context });

    // Show user-friendly notification
    // This would integrate with your notification system
    frontendLoggingService.warning('ErrorHandler', `Error occurred: ${error.message}`);
  };

  return {
    handleError,
  };
}

export default ErrorBoundary;