"use client";
import { useEffect, useRef, useState } from "react";

export type AsyncState<T> = { loading: boolean; error: string | null; data: T | null; reload: () => void };

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<{ loading: boolean; error: string | null; data: T | null }>({
    loading: true, error: null, data: null,
  });
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  useEffect(() => { fnRef.current = fn; });
  const key = JSON.stringify(deps);
  useEffect(() => {
    let alive = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState((s) => ({ ...s, loading: true, error: null }));
    fnRef.current().then(
      (data) => alive && setState({ loading: false, error: null, data }),
      (e: unknown) => alive && setState({ loading: false, error: e instanceof Error ? e.message : "Đã xảy ra lỗi", data: null }),
    );
    return () => { alive = false; };
  }, [key, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}
