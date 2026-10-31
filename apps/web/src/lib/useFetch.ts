import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';

export interface FetchState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/** Tiny data hook: runs `fn` on mount and on `deps` change; optional polling. */
export function useFetch<T>(fn: () => Promise<T>, deps: unknown[] = [], pollMs?: number): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback((silent: boolean) => {
    if (!silent) setLoading(true);
    fnRef
      .current()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e : new ApiError(0, 'network', String(e))))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    run(false);
    if (!pollMs) return;
    const id = window.setInterval(() => run(true), pollMs);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload: () => run(false) };
}
