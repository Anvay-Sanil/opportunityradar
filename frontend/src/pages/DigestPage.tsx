import { useEffect, useState } from 'react';
import {
  Bell,
  Save,
  Loader2,
  Mail,
  Clock,
  Calendar,
  History,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { api, ApiError, getErrorMessage } from '../lib/api';
import { RequestError } from '../components/ui/RequestError';
import { CustomSelect } from '../components/ui/CustomSelect';

const DAYS = [
  'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
];

const FREQUENCIES = ['Weekly', 'Biweekly', 'Monthly'];

export function DigestPage() {
  const [prefs, setPrefs] = useState({
    enabled: true,
    frequency: 'Weekly',
    day: 'Sunday',
    time: '10:00',
    max_results: 5,
    min_match_score: 0,
    include_new_only: true,
  });
  const [scheduleTimezone, setScheduleTimezone] = useState('UTC');
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([
      api.digest.getPreferences(),
      api.digest.getLogs(5),
    ])
      .then(([p, l]) => {
        if (p?.timezone) setScheduleTimezone(p.timezone);
        if (p) setPrefs({
          ...p,
          day: p.day.charAt(0).toUpperCase() + p.day.slice(1),
          frequency: p.frequency.charAt(0).toUpperCase() + p.frequency.slice(1),
        });
        setLogs(l || []);
      })
      .catch((err) => {
        setError(getErrorMessage(err));
        setLoadFailed(true);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...prefs,
        day: prefs.day.toLowerCase(),
        frequency: prefs.frequency.toLowerCase(),
      };
      const updated = await api.digest.updatePreferences(payload);
      setPrefs({
        ...updated,
        day: updated.day.charAt(0).toUpperCase() + updated.day.slice(1),
        frequency: updated.frequency.charAt(0).toUpperCase() + updated.frequency.slice(1),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) { setError(getErrorMessage(err)); } finally {
      setSaving(false);
    }
  };

  if (loadFailed && !loading) return <RequestError message={error || 'Unable to load this page.'} onRetry={() => window.location.reload()} />;

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {error && <RequestError message={error} />}
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center">
          <Bell className="w-7 h-7 text-brand-400" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white">Digest Settings</h1>
          <p className="text-gray-400 mt-1">Get your top internship matches delivered to your inbox</p>
          <p className="text-sm text-gray-400 mt-1">Times are in {scheduleTimezone}. Monthly sends on the first selected weekday of each month.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Toggle */}
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center border ${prefs.enabled ? 'bg-brand-500/10 border-brand-500/20' : 'bg-white/[0.04] border-white/[0.06]'}`}>
                <Mail className={`w-6 h-6 ${prefs.enabled ? 'text-brand-400' : 'text-gray-500'}`} />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Weekly Digest</h2>
                <p className="text-sm text-gray-400">Receive your top matches via email</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={prefs.enabled}
                onChange={(e) => setPrefs({ ...prefs, enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-white/[0.1] peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-brand-500/30 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-white/20 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
            </label>
          </div>
        </div>

        {prefs.enabled && (
          <>
            {/* Schedule */}
            <div className="card p-6 space-y-5">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Calendar className="w-5 h-5 text-brand-400" />
                Schedule
              </h2>

              <div className="grid md:grid-cols-3 gap-4">
                <div>
                  <label className="label">Frequency</label>
                  <CustomSelect
                    value={prefs.frequency}
                    onChange={(v) => setPrefs({ ...prefs, frequency: v })}
                    options={FREQUENCIES}
                    placeholder="Select frequency"
                  />
                </div>
                <div>
                  <label className="label">Day</label>
                  <CustomSelect
                    value={prefs.day}
                    onChange={(v) => setPrefs({ ...prefs, day: v })}
                    options={DAYS}
                    placeholder="Select day"
                  />
                </div>
                <div>
                  <label className="label">Time</label>
                  <input
                    type="time"
                    className="input-field"
                    value={prefs.time}
                    onChange={(e) => setPrefs({ ...prefs, time: e.target.value })}
                  />
                </div>
              </div>
            </div>

            {/* Filters */}
            <div className="card p-6 space-y-5">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Clock className="w-5 h-5 text-brand-400" />
                Content Preferences
              </h2>

              <div className="grid md:grid-cols-3 gap-4">
                <div>
                  <label className="label">Max Results</label>
                  <CustomSelect
                    value={String(prefs.max_results)}
                    onChange={(v) => setPrefs({ ...prefs, max_results: parseInt(v) })}
                    options={['3', '5', '10', '15', '20']}
                    placeholder="Select max"
                  />
                </div>
                <div>
                  <label className="label">Min Match Score</label>
                  <CustomSelect
                    value={String(prefs.min_match_score)}
                    onChange={(v) => setPrefs({ ...prefs, min_match_score: parseFloat(v) })}
                    options={['0', '0.3', '0.5', '0.7']}
                    placeholder="Select min score"
                  />
                </div>
                <div className="flex items-end pb-3">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prefs.include_new_only}
                      onChange={(e) => setPrefs({ ...prefs, include_new_only: e.target.checked })}
                      className="w-4 h-4 rounded border-white/20 bg-white/[0.06] text-brand-500 focus:ring-brand-500/30"
                    />
                    <span className="text-sm font-medium text-gray-300">Only new opportunities</span>
                  </label>
                </div>
              </div>
            </div>
          </>
        )}

        <button type="submit" disabled={saving} className="btn-primary py-3.5 px-8">
          {saving ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : saved ? (
            <><Save className="w-4 h-4 mr-2" /> Saved!</>
          ) : (
            <><Save className="w-4 h-4 mr-2" /> Save Settings</>
          )}
        </button>
      </form>

      {/* Digest History */}
      {logs.length > 0 && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <History className="w-5 h-5 text-brand-400" />
            Recent Digests
          </h2>
          <div className="space-y-3">
            {logs.map((log) => (
              <div key={log.id} className="flex items-center justify-between py-3 px-4 rounded-xl bg-white/[0.03]">
                <div className="flex items-center gap-3">
                  {log.opened ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <XCircle className="w-5 h-5 text-gray-600" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-gray-200">
                      {log.opportunities_count} opportunities
                    </p>
                    <p className="text-xs text-gray-500">
                      {log.error ? 'Attempted' : 'Sent'} {new Date(log.sent_at).toLocaleDateString('en-US', {
                        weekday: 'long',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                </div>
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${log.opened ? 'bg-emerald-500/10 text-emerald-300' : 'bg-white/[0.06] text-gray-400'}`}>
                  {log.error ? 'Failed' : log.opened ? 'Opened' : 'Sent'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
