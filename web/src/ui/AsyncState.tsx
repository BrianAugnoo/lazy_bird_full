import type { ReactNode } from 'react';

interface AsyncStateProps<T> {
  loading: boolean;
  error: Error | null;
  data: T | undefined;
  /** True when the data is empty (default: empty array). */
  isEmpty?: (data: T) => boolean;
  empty?: ReactNode;
  onRetry?: () => void;
  children: (data: T) => ReactNode;
}

/** Shows loading, error (with retry) and empty states, then the content. */
export function AsyncState<T>({ loading, error, data, isEmpty, empty, onRetry, children }: AsyncStateProps<T>) {
  if (error && data === undefined) {
    return (
      <div className="state-error" role="alert">
        <div className="state-title">Could not load this</div>
        <p className="state-desc">{error.message}</p>
        {onRetry && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    );
  }
  if (data === undefined) {
    return loading ? (
      <div className="state-loading" aria-live="polite">
        <span className="spinner" />
        <span>Loading…</span>
      </div>
    ) : null;
  }
  const emptyCheck = isEmpty ?? ((value: T) => Array.isArray(value) && value.length === 0);
  if (emptyCheck(data) && empty) return <div className="state-empty">{empty}</div>;
  return <>{children(data)}</>;
}
