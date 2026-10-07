import { useCallback, useEffect, useRef, useState } from 'react';

export interface Resource<T> {
  data: T | undefined;
  error: Error | null;
  loading: boolean;
  /** Load again; resolves once done. Keeps showing the previous data meanwhile. */
  reload: () => Promise<void>;
  /** Replace the data locally (e.g. after a mutation returned the new value). */
  setData: (value: T | undefined | ((previous: T | undefined) => T | undefined)) => void;
}

/**
 * Load data with `loader` when the component mounts and whenever `deps` change.
 * Responses of outdated loads are ignored.
 */
export function useResource<T>(loader: () => Promise<T>, deps: unknown[] = []): Resource<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const value = await loaderRef.current();
      if (current === generation.current) {
        setData(value);
        setError(null);
      }
    } catch (reason) {
      if (current === generation.current) setError(reason instanceof Error ? reason : new Error(String(reason)));
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload, setData: setData as Resource<T>['setData'] };
}
