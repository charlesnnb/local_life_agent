import React, { useState, useEffect } from 'react';
import QueryInput from './components/QueryInput';
import { planQueryV2, PlanResponseV2, ProviderStatus, getProviderStatus } from './api';

const App: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PlanResponseV2 | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiVersion, setApiVersion] = useState<'v1' | 'v2'>('v2');
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);
  const [appMode, setAppMode] = useState<string>('loading...');

  useEffect(() => {
    getProviderStatus().then(s => {
      setProviderStatus(s.provider_status);
      setAppMode(s.app_mode);
    }).catch(() => {});
  }, []);

  const handlePlan = async (query: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await planQueryV2('u_001', query);
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-3xl">🏠</span>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Local Life Planning Agent</h1>
                <p className="text-sm text-gray-500">
                  真实动态本地生活方案推荐 · {apiVersion === 'v2' ? 'Provider V2' : 'Legacy V1'}
                </p>
              </div>
            </div>
            {/* Provider Status Bar */}
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                appMode === 'demo' ? 'bg-green-100 text-green-700' :
                appMode === 'development' ? 'bg-yellow-100 text-yellow-700' :
                'bg-gray-100 text-gray-700'
              }`}>
                {appMode}
              </span>
              <span className="text-xs text-gray-400">|</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${providerStatus?.llm === 'real' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-500'}`}>
                LLM:{providerStatus?.llm || '...'}
              </span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${providerStatus?.poi === 'real' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-500'}`}>
                POI:{providerStatus?.poi || '...'}
              </span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${providerStatus?.weather === 'real' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-500'}`}>
                W:{providerStatus?.weather || '...'}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <QueryInput onPlan={handlePlan} loading={loading} />

        {error && (
          <div className="card border-red-200 bg-red-50">
            <p className="text-sm text-red-700 flex items-center gap-2"><span>❌</span> {error}</p>
          </div>
        )}

        {loading && (
          <div className="card">
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded w-1/3" />
              <div className="h-3 bg-gray-200 rounded w-2/3" />
              <div className="h-3 bg-gray-200 rounded w-1/2" />
            </div>
          </div>
        )}

        {result && (
          <>
            {/* Status + Provider Info */}
            <div className="card flex items-center gap-4 flex-wrap">
              <span className={`badge text-sm ${result.status === 'success' ? 'badge-green' : 'badge-red'}`}>
                {result.status === 'success' ? '成功' : '失败'}
              </span>
              <span className="badge badge-blue">{result.scene || '场景未指定'}</span>
              <span className="text-xs text-gray-400">
                {Object.entries(result.provider_status).map(([k, v]) => (
                  <span key={k} className="mr-2">{k}: <b className={v === 'real' ? 'text-green-600' : 'text-gray-500'}>{v}</b></span>
                ))}
              </span>
              <span className="text-xs text-gray-400 ml-auto">
                confidence: {(result.parsed_intent?.confidence ?? 0).toFixed(2)}
              </span>
            </div>

            {/* Summary / Explanation */}
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">推荐方案</h3>
              <p className="text-sm text-gray-600 whitespace-pre-line">{result.summary}</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Parsed Intent */}
              <div className="card">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">📋 意图解析</h3>
                <div className="space-y-1.5 text-xs">
                  {result.parsed_intent && Object.entries(result.parsed_intent).map(([k, v]) => {
                    if (k === 'raw_user_input' || k === 'missing_fields') return null;
                    const isMissing = result.parsed_intent.missing_fields?.includes(k);
                    return (
                      <div key={k} className="flex justify-between">
                        <span className="text-gray-500">{k}</span>
                        <span className={isMissing ? 'text-orange-400 italic' : 'text-gray-800'}>
                          {v === null ? <span className="text-orange-400">unknown</span> :
                           typeof v === 'boolean' ? (v ? '是' : '否') :
                           Array.isArray(v) ? (v.length ? v.join(', ') : <span className="text-orange-400">empty</span>) :
                           String(v)}
                        </span>
                      </div>
                    );
                  })}
                </div>
                {result.parsed_intent?.missing_fields?.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-gray-100">
                    <p className="text-xs text-orange-500">
                      ⚠ 未提供信息: {result.parsed_intent.missing_fields.join(', ')}
                    </p>
                  </div>
                )}
              </div>

              {/* Weather */}
              <div className="card">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">🌤 天气</h3>
                {result.weather ? (
                  <div className="text-sm space-y-1">
                    <p>{result.weather.city}: {result.weather.day_weather} {result.weather.day_temp}°C / {result.weather.night_temp}°C</p>
                    <p className="text-xs text-gray-400">Source: {result.weather.source}</p>
                  </div>
                ) : (
                  <p className="text-xs text-gray-400">天气数据不可用</p>
                )}
              </div>
            </div>

            {/* Score Breakdown */}
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">📊 评分分解 (Score Breakdown)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-2 pr-3">候选</th>
                      <th className="pb-2 pr-3">距离</th>
                      <th className="pb-2 pr-3">路线</th>
                      <th className="pb-2 pr-3">预算</th>
                      <th className="pb-2 pr-3">场景</th>
                      <th className="pb-2 pr-3">天气</th>
                      <th className="pb-2 pr-3">偏好</th>
                      <th className="pb-2 pr-3">未知扣分</th>
                      <th className="pb-2 font-bold">总分</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rankings?.poi_rankings?.map((r, i) => (
                      <tr key={i} className={i === 0 ? 'bg-blue-50' : ''}>
                        <td className="py-1.5 pr-3 font-medium">{r.candidate_name}{i === 0 ? ' 🏆' : ''}</td>
                        <td className="py-1.5 pr-3">{r.distance_score.toFixed(2)}</td>
                        <td className="py-1.5 pr-3">{r.route_time_score.toFixed(2)}</td>
                        <td className="py-1.5 pr-3">{r.budget_score.toFixed(2)}</td>
                        <td className="py-1.5 pr-3">{r.scene_score.toFixed(2)}</td>
                        <td className="py-1.5 pr-3">{r.weather_score.toFixed(2)}</td>
                        <td className="py-1.5 pr-3">{r.preference_score.toFixed(2)}</td>
                        <td className="py-1.5 pr-3 text-orange-500">-{r.unknown_penalty.toFixed(2)}</td>
                        <td className="py-1.5 font-bold">{r.final_score.toFixed(2)}</td>
                      </tr>
                    ))}
                    {(!result.rankings?.poi_rankings || result.rankings.poi_rankings.length === 0) && (
                      <tr><td colSpan={9} className="py-2 text-gray-400">无POI候选</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {result.rankings?.restaurant_rankings?.length > 0 && (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-gray-500 border-b">
                        <th className="pb-2 pr-3">餐厅候选</th>
                        <th className="pb-2 pr-3">距离</th>
                        <th className="pb-2 pr-3">路线</th>
                        <th className="pb-2 pr-3">预算</th>
                        <th className="pb-2 pr-3">场景</th>
                        <th className="pb-2 pr-3">天气</th>
                        <th className="pb-2 pr-3">偏好</th>
                        <th className="pb-2 pr-3">未知扣分</th>
                        <th className="pb-2 font-bold">总分</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.rankings.restaurant_rankings.map((r, i) => (
                        <tr key={i} className={i === 0 ? 'bg-blue-50' : ''}>
                          <td className="py-1.5 pr-3 font-medium">{r.candidate_name}{i === 0 ? ' 🏆' : ''}</td>
                          <td className="py-1.5 pr-3">{r.distance_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.route_time_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.budget_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.scene_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.weather_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.preference_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3 text-orange-500">-{r.unknown_penalty.toFixed(2)}</td>
                          <td className="py-1.5 font-bold">{r.final_score.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Candidates with Data Sources */}
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">📍 候选地点 (Data Source)</h3>
              <div className="space-y-3">
                {(result.candidates?.pois || []).slice(0, 5).map((poi, i) => (
                  <CandidateCard key={i} candidate={poi} rank={i + 1} isTop={i === 0} />
                ))}
                {(result.candidates?.restaurants || []).slice(0, 5).map((r, i) => (
                  <CandidateCard key={`r${i}`} candidate={r} rank={i + 1} isTop={i === 0} />
                ))}
              </div>
            </div>

            {/* Itinerary */}
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">🗺 行程方案</h3>
              <div className="space-y-2">
                {result.itinerary.map((item, i) => (
                  <div key={i} className="flex items-start gap-3 p-2 rounded-lg bg-gray-50">
                    <span className={`mt-0.5 text-xs px-2 py-0.5 rounded-full ${
                      item.type === 'travel' ? 'bg-blue-100 text-blue-600' :
                      item.type === 'activity' ? 'bg-green-100 text-green-600' :
                      item.type === 'meal' ? 'bg-orange-100 text-orange-600' :
                      'bg-gray-200 text-gray-600'
                    }`}>
                      {item.type}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-gray-800">{item.title}</p>
                      {item.description && <p className="text-xs text-gray-500">{item.description}</p>}
                    </div>
                    {item.time && <span className="text-xs text-gray-400 ml-auto">{item.time}</span>}
                  </div>
                ))}
              </div>
            </div>

            {/* Unknown Fields Summary */}
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">❓ Unknown 字段</h3>
              <p className="text-xs text-gray-500">
                以下字段在当前数据源中均为 unknown（AMap 不提供评分/人均/营业时间等）：
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {['rating', 'avg_price', 'open_time', 'close_time', 'booking_supported'].map(f => (
                  <span key={f} className="text-xs px-2 py-0.5 rounded bg-orange-50 text-orange-600 border border-orange-200">
                    {f} = unknown
                  </span>
                ))}
              </div>
            </div>

            {/* Trace */}
            <details className="card">
              <summary className="text-sm font-semibold text-gray-700 cursor-pointer">规划过程 (Trace)</summary>
              <div className="mt-3 space-y-1 max-h-80 overflow-y-auto">
                {result.planning_trace.map((t, i) => (
                  <div key={i} className="text-xs text-gray-500 py-1 border-b border-gray-50">
                    <span className="font-medium text-gray-600">[{t.phase}]</span> {t.message}
                  </div>
                ))}
              </div>
            </details>
          </>
        )}
      </main>

      <footer className="text-center py-6 text-xs text-gray-400">
        Local Life Planning Agent · V2 Provider Architecture · Built for Competition
      </footer>
    </div>
  );
};

// Candidate card showing data source and unknown fields
const CandidateCard: React.FC<{ candidate: any; rank: number; isTop: boolean }> = ({ candidate, rank, isTop }) => {
  const unknownFields = Object.entries(candidate)
    .filter(([, v]) => v === 'unknown' || v === null)
    .map(([k]) => k);

  return (
    <div className={`p-3 rounded-lg border ${isTop ? 'border-blue-200 bg-blue-50/50' : 'border-gray-100'}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${isTop ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>
          #{rank}
        </span>
        <span className="font-medium text-sm text-gray-800">{candidate.name}</span>
        <span className={`text-xs px-1.5 py-0.5 rounded ${
          candidate.source === 'amap' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-500'
        }`}>
          src:{candidate.source}
        </span>
        {isTop && <span className="text-xs">🏆</span>}
      </div>
      <div className="text-xs text-gray-500 space-y-0.5">
        {candidate.address && <p>📍 {candidate.address}</p>}
        {candidate.type && candidate.type !== 'unknown' && <p>🏷 {candidate.type}</p>}
        {candidate.tel && <p>📞 {candidate.tel}</p>}
        {candidate.distance_m != null && <p>📏 {candidate.distance_m}m</p>}
      </div>
      {unknownFields.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {unknownFields.filter(f => f !== 'raw' && f !== 'source').slice(0, 8).map(f => (
            <span key={f} className="text-[10px] px-1 py-0.5 rounded bg-orange-50 text-orange-500 border border-orange-100">
              {f}=?
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default App;
