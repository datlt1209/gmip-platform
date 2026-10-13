export function Loading({ label = "Đang tải dữ liệu…", rows = 0 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite">
      {rows > 0 ? (
        <div className="grid">{Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" />)}</div>
      ) : (
        <p className="state">{label}</p>
      )}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      <p>⚠ {message}</p>
      {onRetry && <button className="btn" onClick={onRetry}>Thử lại</button>}
    </div>
  );
}

export function Empty({ message }: { message: string }) {
  return <p className="state">{message}</p>;
}
