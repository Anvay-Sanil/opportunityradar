import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Briefcase,
  FileCheck,
  AlertCircle,
  ArrowRight,
  Zap,
  Target,
  Rocket,
  Radar,
} from 'lucide-react';
import { useAuth } from '../lib/auth';
import { api, ApiError, getErrorMessage } from '../lib/api';
import { RequestError } from '../components/ui/RequestError';

export function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<any>(null);
  const [matches, setMatches] = useState<any[]>([]);
  const [profileExists, setProfileExists] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [profile, appStats, matchedOpps] = await Promise.all([
          api.profile.get().catch((err) => { if (err instanceof ApiError && err.status === 404) return null; throw err; }),
          api.applications.stats(),
          api.opportunities.getMatches({ page_size: '5' }).catch((err) => { if (err instanceof ApiError && err.status === 400) return null; throw err; }),
        ]);
        setProfileExists(!!profile);
        setStats(appStats);
        setMatches(matchedOpps?.items || []);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) return <RequestError message={error} onRetry={() => window.location.reload()} />;

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Welcome */}
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center">
          <Radar className="w-7 h-7 text-brand-400" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white">
            Hey, {user?.full_name?.split(' ')[0]}
          </h1>
          <p className="text-gray-400 mt-1">Here's your internship landscape.</p>
        </div>
      </div>

      {/* Profile Setup CTA */}
      {!profileExists && (
        <div className="rounded-2xl bg-amber-500/10 border border-amber-500/20 p-6 flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
            <AlertCircle className="w-5 h-5 text-amber-400" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-amber-300">Complete your profile to get AI-matched opportunities</h3>
            <p className="text-amber-400/70 text-sm mt-1">Add your skills, year, branch, and preferences so we can find the perfect internships for you.</p>
          </div>
          <Link to="/profile" className="btn-primary text-sm py-2.5 px-5 bg-amber-500 hover:bg-amber-600 shadow-amber-500/20 shrink-0">
            Set Up Profile
            <ArrowRight className="ml-2 w-4 h-4" />
          </Link>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            icon: Briefcase,
            label: 'Available Opportunities',
            value: matches.length > 0 ? matches.length + '+' : '—',
            color: 'bg-brand-500/10 text-brand-400 border-brand-500/20',
          },
          {
            icon: FileCheck,
            label: 'Applications',
            value: stats?.total ?? 0,
            color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
          },
          {
            icon: Rocket,
            label: 'Young Startups',
            value: matches.filter((m: any) => m.company_funding_stage).length || '—',
            color: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
          },
          {
            icon: Target,
            label: 'Match Score Avg',
            value: matches.length > 0
              ? Math.round(matches.reduce((a: number, b: any) => a + (b.match_score || 0) * 100, 0) / matches.length) + '%'
              : '—',
            color: 'bg-brand-500/10 text-brand-400 border-brand-500/20',
          },
        ].map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="card p-5">
            <div className={`w-10 h-10 rounded-xl ${color} border flex items-center justify-center mb-3`}>
              <Icon className="w-5 h-5" />
            </div>
            <p className="text-2xl font-bold text-white">{value}</p>
            <p className="text-sm text-gray-400 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Matched Opportunities */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-white">Your Top Matches</h2>
            <p className="text-sm text-gray-400 mt-1">AI-ranked opportunities tailored to your profile</p>
          </div>
          <Link to="/opportunities" className="text-brand-400 text-sm font-medium hover:text-brand-300 flex items-center gap-1 transition-colors">
            View All <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {matches.length === 0 ? (
          <div className="text-center py-12">
            <Zap className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-500">No matches yet{profileExists ? '' : ' — set up your profile first'}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {matches.slice(0, 5).map((opp: any) => {
              const score = Math.round((opp.match_score || 0) * 100);
              const scoreClass = score >= 75 ? 'match-score-high' : score >= 50 ? 'match-score-med' : 'match-score-low';
              return (
                <Link
                  key={opp.id}
                  to={`/opportunities/${opp.id}`}
                  className="flex items-center gap-4 p-4 rounded-xl hover:bg-white/[0.03] transition-colors group"
                >
                  <div className={`match-score ${scoreClass}`}>{score}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-gray-100 truncate group-hover:text-white transition-colors">{opp.title}</p>
                      {opp.company_funding_stage && (
                        <span className="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-brand-500/10 text-brand-300 border border-brand-500/20">
                          <Rocket className="w-2.5 h-2.5" />
                          Startup
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-400">{opp.company} — {opp.location || 'Remote'}</p>
                    {opp.match_reason && (
                      <div>
                        <p className="text-sm text-gray-500 mt-1 truncate">{opp.match_reason}</p>
                        {opp.skill_gaps && opp.skill_gaps.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap mt-1">
                            {opp.skill_gaps.slice(0, 2).map((skill: string) => (
                              <span key={skill} className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-300/80 border border-amber-500/20">
                                Learn {skill}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    {opp.stipend && <span>{opp.stipend}</span>}
                    <ArrowRight className="w-4 h-4 text-gray-600 group-hover:text-gray-400 transition-colors" />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Application Status */}
      {stats && stats.total > 0 && (
        <div className="card p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Application Pipeline</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { label: 'Saved', value: stats.saved, color: 'bg-white/[0.06] text-gray-300' },
              { label: 'Applied', value: stats.applied, color: 'bg-blue-500/10 text-blue-300' },
              { label: 'Interview', value: stats.interview, color: 'bg-purple-500/10 text-purple-300' },
              { label: 'Offered', value: stats.offered, color: 'bg-emerald-500/10 text-emerald-300' },
              { label: 'Rejected', value: stats.rejected, color: 'bg-red-500/10 text-red-300' },
            ].map(({ label, value, color }) => (
              <div key={label} className="text-center p-4 rounded-xl bg-white/[0.03]">
                <div className={`text-2xl font-bold ${color.split(' ')[1]}`}>{value || 0}</div>
                <p className="text-sm text-gray-500 mt-1">{label}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
