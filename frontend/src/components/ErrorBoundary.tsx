import React from 'react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onError?: (error: Error, info: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
  };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, info);
    // Call custom error handler if provided
    if (this.props.onError) {
      try {
        this.props.onError(error, info);
      } catch (callbackError) {
        console.error('Error in onError callback:', callbackError);
      }
    }
  }

  private handleReload = () => {
    window.location.reload();
  };

  render() {
    const { hasError } = this.state;
    const { children, fallback } = this.props;

    if (hasError) {
      if (fallback && typeof fallback !== 'string' && React.isValidElement(fallback)) {
        return fallback;
      }

      const fallbackMessage =
        typeof fallback === 'string'
          ? fallback
          : 'Something went wrong while loading this section.';

      return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 p-6 text-center">
          <div className="text-base font-poppins text-brand-700">
            {fallbackMessage}
          </div>
          <button
            type="button"
            onClick={this.handleReload}
            className="px-5 py-2 rounded-lg bg-brand-700 text-white font-poppins text-sm font-semibold shadow-md transition-colors hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500"
          >
            Reload page
          </button>
        </div>
      );
    }

    return children;
  }
}

export default ErrorBoundary;
