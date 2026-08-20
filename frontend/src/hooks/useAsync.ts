import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError } from '@/services/apiClient';

export type AsyncState<T> =
  | { status: 'loading'; data: null; error: null }
  | { status: 'success'; data: T; error: null }
  | { status: 'error'; data: null; error: ApiError };

const LOADING = { status: 'loading', data: null, error: null } as const;

/** Identity of one execution of the async function. */
interface RunToken {
  key: string;
  nonce: number;
}

/** A settled result tagged with the run it came from, so stale ones are ignored. */
interface Settled<T> {
  run: RunToken;
  state: AsyncState<T>;
}

/**
 * Run an abortable async function and expose an explicit state machine, so
 * components render distinct loading / success / error states rather than
 * guessing from nullable values.
 *
 * `loading` is *derived* during render (the settled result belongs to an older
 * run) instead of being written from inside the effect, which avoids a
 * cascading re-render on every refetch.
 *
 * @param fn  Receives an `AbortSignal`; the in-flight request is aborted when
 *            the component unmounts or `key` changes.
 * @param key Identifies the request. Changing it starts a new run — build it
 *            from whatever the request depends on, e.g. `` `report:${id}` ``.
 */
export function useAsync<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  key = 'default',
): AsyncState<T> & { reload: () => void } {
  const [nonce, setNonce] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);

  // A fresh object identity per run; comparing it tells us if `settled` is stale.
  const run = useMemo(() => ({ key, nonce }), [key, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    const controller = new AbortController();

    fn(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setSettled({ run, state: { status: 'success', data, error: null } });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setSettled({
          run,
          state: {
            status: 'error',
            data: null,
            error: error instanceof ApiError ? error : new ApiError('Request failed', 'unknown'),
          },
        });
      });

    return () => controller.abort();
    // `fn` is intentionally excluded: callers pass an inline closure, and `run`
    // already encodes every input the request depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run]);

  const state: AsyncState<T> = settled?.run === run ? settled.state : LOADING;

  return { ...state, reload };
}
