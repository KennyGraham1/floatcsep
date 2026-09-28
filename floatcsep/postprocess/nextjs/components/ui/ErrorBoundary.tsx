'use client';

import { Component, type ErrorInfo, type ReactNode } from 'react';
import { ErrorState } from './States';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** What failed, e.g. "The map". */
  label?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/** Keeps a failing chart or map from taking the rest of the page down. */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Dashboard component failed:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <ErrorState
          title={`${this.props.label ?? 'This view'} could not be displayed`}
          message={this.state.error.message}
          details={this.state.error.stack}
          onRetry={() => this.setState({ error: null })}
        />
      );
    }
    return this.props.children;
  }
}
