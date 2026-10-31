import type { ApiError } from '../api/client';
import { s } from '../strings';

export function Skeleton({ h = 80 }: { h?: number }) {
  return <div className="skel" style={{ height: h }} aria-hidden="true" />;
}

export function Loading({ blocks = 3 }: { blocks?: number }) {
  return (
    <div className="stack" role="status" aria-label={s.common.loading}>
      {Array.from({ length: blocks }, (_, i) => <Skeleton key={i} h={i === 0 ? 110 : 70} />)}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: ApiError | null; onRetry?: () => void }) {
  const msg = error?.code === 'network' ? s.common.networkError : error?.message || s.common.genericError;
  return (
    <div className="empty" role="alert">
      <p className="err">{msg}</p>
      {onRetry && <button className="btn ghost small" onClick={onRetry}>{s.common.retry}</button>}
    </div>
  );
}

export function Empty({ text, action }: { text: string; action?: React.ReactNode }) {
  return (
    <div className="empty">
      <p>{text}</p>
      {action}
    </div>
  );
}
