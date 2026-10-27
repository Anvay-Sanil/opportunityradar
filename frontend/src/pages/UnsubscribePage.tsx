import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, getErrorMessage } from '../lib/api';
import { RequestError } from '../components/ui/RequestError';

export function UnsubscribePage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [ready, setReady] = useState(false);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    api.digest.checkUnsubscribe(token)
      .then(() => { if (active) setReady(true); })
      .catch((err) => { if (active) setError(getErrorMessage(err)); });
    return () => { active = false; };
  }, [token]);
  async function confirm() {
    setBusy(true);
    setError(null);
    try { await api.digest.unsubscribe(token); setDone(true); }
    catch (err) { setError(getErrorMessage(err)); }
    finally { setBusy(false); }
  }
  return <main className="max-w-lg mx-auto py-24 px-6 space-y-6">
    <h1 className="text-3xl font-bold text-white">{done ? 'You are unsubscribed' : 'Unsubscribe from digests'}</h1>
    {error && <RequestError message={error} />}
    <p className="text-gray-300">{done ? 'You will no longer receive internship digests. You can enable them again in Digest Settings.' : 'Confirm to stop receiving internship digests.'}</p>
    {ready && !done && <button onClick={confirm} disabled={busy} className="btn-primary">{busy ? 'Saving…' : 'Unsubscribe'}</button>}
    <Link to="/" className="block text-brand-400">Back to OpportunityRadar</Link>
  </main>;
}
