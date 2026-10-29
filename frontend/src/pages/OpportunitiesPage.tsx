import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Search,
  SlidersHorizontal,
  MapPin,
  Banknote,
  Building2,
  ExternalLink,
  BookmarkPlus,
  Check,
  Loader2,
  Globe,
  Briefcase,
  Rocket,
} from 'lucide-react';
import { api, ApiError, getErrorMessage } from '../lib/api';
import { RequestError } from '../components/ui/RequestError';
import { CustomSelect } from '../components/ui/CustomSelect';

const SOURCE_ICONS: Record<string, typeof Briefcase> = {
  internshala: Briefcase,
  linkedin: Building2,
  wellfound: Globe,
};

const SOURCE_COLORS: Record<string, string> = {
  internshala: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  linkedin: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  wellfound: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
};

export function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [catalogTotal, setCatalogTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [search, setSearch] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [workModeFilter, setWorkModeFilter] = useState('');
  const [startupOnly, setStartupOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setLoadFailed(false);
    try {
      const params: Record<string, string | number> = { page, page_size: 20 };
      if (search) params.search = search;
      if (sourceFilter) params.source = sourceFilter;
      if (workModeFilter) params.work_mode = workModeFilter;
      if (startupOnly) params.founded_within_months = 36;
      const res = await api.opportunities.list(params);
      setOpportunities(res.items);
      setTotal(res.total);
      setCatalogTotal(res.catalog_total ?? res.total);
      setTotalPages(res.total_pages);
    } catch (err) {
      setError(getErrorMessage(err));
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }, [page, search, sourceFilter, workModeFilter, startupOnly]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async (oppId: string) => {
    setSaving(oppId);
    setError(null);
    try {
      await api.applications.create({ opportunity_id: oppId });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(null);
    }
  };

  if (loadFailed && !loading) return <RequestError message={error || 'Unable to load opportunities.'} onRetry={load} />;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {error && <RequestError message={error} />}
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center">
          <Briefcase className="w-7 h-7 text-brand-400" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white">Opportunities</h1>
          <p className="text-gray-400 mt-1">{total} internships {search || sourceFilter || workModeFilter || startupOnly ? 'match your filters' : 'found across all sources'}</p>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="card p-4">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              className="input-field pl-10"
              placeholder="Search by title, company, skills..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`btn-secondary shrink-0 ${showFilters ? 'bg-brand-500/10 border-brand-500/30 text-brand-300' : ''}`}
          >
            <SlidersHorizontal className="w-4 h-4 mr-2" />
            Filters
          </button>
        </div>

        {showFilters && (
          <div className="flex flex-wrap items-center gap-3 mt-4 pt-4 border-t border-white/[0.06]">
            <div className="w-44">
              <CustomSelect
                value={sourceFilter}
                onChange={(v) => { setSourceFilter(v); setPage(1); }}
                options={['', 'greenhouse', 'internshala', 'linkedin', 'wellfound', 'yc']}
                placeholder="All Sources"
              />
            </div>
            <div className="w-44">
              <CustomSelect
                value={workModeFilter}
                onChange={(v) => { setWorkModeFilter(v); setPage(1); }}
                options={['', 'remote', 'hybrid', 'onsite']}
                placeholder="All Modes"
              />
            </div>
            <button
              onClick={() => { setStartupOnly(!startupOnly); setPage(1); }}
              className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium border transition-all ${
                startupOnly
                  ? 'bg-brand-500/10 text-brand-300 border-brand-500/30'
                  : 'bg-white/[0.04] text-gray-400 border-white/[0.06] hover:border-white/[0.15] hover:text-gray-200'
              }`}
            >
              <Rocket className="w-4 h-4" />
              Young Startups Only
            </button>
          </div>
        )}
      </div>

      {/* Results */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
        </div>
      ) : opportunities.length === 0 ? (
        <div className="card p-12 text-center">
          <Briefcase className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400 text-lg">{catalogTotal === 0 ? 'No internships have been imported yet' : 'No opportunities match your criteria'}</p>
          <p className="text-gray-500 text-sm mt-1">{catalogTotal === 0 ? 'Check back shortly for new employer postings.' : 'Try adjusting your filters. Company age is only available when the source provides it.'}</p>
          <button className="btn-secondary mt-4" onClick={() => {
            if (search || sourceFilter || workModeFilter || startupOnly || page !== 1) {
              setSearch(''); setSourceFilter(''); setWorkModeFilter(''); setStartupOnly(false); setPage(1);
            } else { load(); }
          }}>{catalogTotal === 0 ? 'Refresh listings' : 'Clear filters'}</button>
        </div>
      ) : (
        <div className="grid gap-4">
          {opportunities.map((opp) => {
            const score = Math.round((opp.match_score || 0) * 100);
            const scoreClass = score >= 75 ? 'match-score-high' : score >= 50 ? 'match-score-med' : 'match-score-low';
            const SourceIcon = SOURCE_ICONS[opp.source] || Briefcase;

            return (
              <div key={opp.id} className="card-hover p-5">
                <div className="flex items-start gap-4">
                  {/* Score */}
                  <div className={`match-score ${scoreClass} hidden sm:flex`}>{score}</div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <Link
                          to={`/opportunities/${opp.id}`}
                          className="text-lg font-semibold text-gray-100 hover:text-brand-400 transition-colors"
                        >
                          {opp.title}
                        </Link>
                        <p className="text-brand-400 font-medium text-sm mt-0.5">{opp.company}</p>
                      </div>
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${SOURCE_COLORS[opp.source] || 'bg-white/[0.06] text-gray-400'}`}>
                        <SourceIcon className="w-3 h-3" />
                        {opp.source}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-gray-400">
                      {opp.location && (
                        <span className="flex items-center gap-1.5">
                          <MapPin className="w-3.5 h-3.5" />
                          {opp.location}
                        </span>
                      )}
                      {opp.stipend && (
                        <span className="flex items-center gap-1.5">
                          <Banknote className="w-3.5 h-3.5" />
                          {opp.stipend}
                        </span>
                      )}
                      <span className="flex items-center gap-1.5">
                        <Building2 className="w-3.5 h-3.5" />
                        {opp.work_mode || 'Remote'}
                      </span>
                    </div>

                    {opp.match_reason && (
                      <div className="mt-3 text-sm text-gray-400 bg-white/[0.03] border border-white/[0.06] rounded-lg p-3 space-y-2">
                        <p>{opp.match_reason}</p>
                        {opp.skill_gaps && opp.skill_gaps.length > 0 && (
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-amber-400/70 text-xs font-medium">Learn</span>
                            {opp.skill_gaps.slice(0, 3).map((skill: string) => (
                              <span key={skill} className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20">
                                {skill}
                              </span>
                            ))}
                            {opp.skill_gaps.length > 3 && (
                              <span className="text-xs text-gray-500">+{opp.skill_gaps.length - 3} more</span>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Startup badge */}
                    {opp.company_funding_stage && (
                      <div className="mt-3 flex items-center gap-2">
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-brand-500/10 text-brand-300 border border-brand-500/20">
                          <Rocket className="w-3 h-3" />
                          {opp.company_funding_stage}
                        </span>
                        {opp.company_age_months && (
                          <span className="text-xs text-gray-500">
                            {Math.round(opp.company_age_months)} months old
                          </span>
                        )}
                      </div>
                    )}

                    {/* Skills */}
                    {opp.skills_required?.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {opp.skills_required.slice(0, 5).map((skill: string) => (
                          <span key={skill} className="px-2.5 py-1 bg-white/[0.06] text-gray-300 rounded-lg text-xs font-medium">
                            {skill}
                          </span>
                        ))}
                        {opp.skills_required.length > 5 && (
                          <span className="px-2.5 py-1 text-gray-500 text-xs">
                            +{opp.skills_required.length - 5} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={() => handleSave(opp.id)}
                      disabled={saving === opp.id}
                      className="btn-secondary text-sm py-2 px-3"
                      title="Save opportunity"
                    >
                      {saving === opp.id ? (
                        <Check className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <BookmarkPlus className="w-4 h-4" />
                      )}
                    </button>
                    <a
                      href={opp.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-primary text-sm py-2 px-3"
                      title="Open original listing"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-secondary text-sm py-2 px-4"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500 px-4">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn-secondary text-sm py-2 px-4"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
