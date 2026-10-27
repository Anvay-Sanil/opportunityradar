export function RequestError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5 text-red-200">
    <p>{message}</p>
    {onRetry && <button type="button" onClick={onRetry} className="btn-secondary mt-3">Try again</button>}
  </div>;
}
