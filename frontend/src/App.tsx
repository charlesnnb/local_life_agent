import React, { useState, useEffect, useRef, useCallback } from 'react';
import AgentTracePanel from './components/AgentTracePanel';
import ToolCallTimeline from './components/ToolCallTimeline';
import OrderResultCard from './components/OrderResultCard';
import ShareMessageBox from './components/ShareMessageBox';
import {
  planQuery, planQueryStream,
  PlanResponseV2, ProviderStatus, SSEEvent, UserLocation, ToolCall,
  CompletedAction, FallbackAction,
  getProviderStatus, getProviderStatusV2, ProviderStatusV2,
  switchAppMode,
} from './api';

const FAMILY_EXAMPLE = '今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远，帮我安排一下。';
const FRIENDS_EXAMPLE = '今天下午我们4个人，2男2女，想出去玩几个小时，顺便吃饭，别太远。';

const SCENARIO_OPTIONS: [string, string, string][] = [
  ['normal', '正常', ''],
  ['restaurant_full', '餐厅无位', '模拟17:00餐厅满座，触发时间切换fallback'],
  ['rainy_weather', '雨天室内', '强制雨天，验证室内活动优先逻辑'],
  ['ticket_sold_out', '门票售罄', '模拟门票不足，切换到备选POI'],
  ['optional_service_fail', '蛋糕失败', '模拟蛋糕/咖啡下单失败，不影响主流程'],
  ['route_too_far', '路线太远', '模拟首选距离过远，选择更近候选'],
];

const ADDRESS_OPTIONS = [
  { value: '', label: '默认地址' },
  { value: '上海徐汇区', label: '上海徐汇区' },
  { value: '上海静安区', label: '上海静安区' },
  { value: '上海黄浦区', label: '上海黄浦区' },
  { value: '北京朝阳区', label: '北京朝阳区' },
  { value: '广州天河区', label: '广州天河区' },
  { value: '深圳南山区', label: '深圳南山区' },
];

// ── Text sanitizer: remove markdown artifacts ──────────────────────
function sanitizeText(text: string): string {
  if (!text) return text;
  return text
    .replace(/\*\*/g, '')
    .replace(/###/g, '')
    .replace(/```/g, '')
    .replace(/^\s*[-*]\s/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// ── Provider chip ────────────────────────────────────────────────
function ProviderChip({ label, value }: { label: string; value?: string }) {
  const isReal = value === 'real';
  return (
    <span className={`chip ${isReal ? 'chip-on' : 'chip-off'}`} title={`${label}: ${value || '?'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${isReal ? 'bg-emerald-500' : 'bg-gray-300'}`} />
      {label}
    </span>
  );
}

// ── Location source display ───────────────────────────────────────
function LocationSourceLabel({ loc }: { loc: any }) {
  if (!loc) return null;
  const source = loc.source || '';
  let label = '';
  let emoji = '';
  if (source === 'browser_geolocation') { label = '浏览器定位'; emoji = '📍'; }
  else if (source === 'manual') { label = '手动输入'; emoji = '📍'; }
  else if (source === 'query_extracted') { label = '用户输入识别'; emoji = '📍'; }
  else if (source === 'profile_default') { label = '用户默认地址'; emoji = '📍'; }
  else if (source === 'system_default') { label = '系统默认'; emoji = '📍'; }
  else return null;

  const address = loc.address || (loc.lat ? `${loc.lat.toFixed(4)}, ${loc.lng.toFixed(4)}` : '');
  const accuracy = loc.accuracy ? (loc.accuracy > 1000 ? ' (精度较低)' : ` (精度约${Math.round(loc.accuracy)}m)`) : '';

  return (
    <span className="chip bg-blue-50 text-blue-700 border-blue-200">
      {emoji} 当前出发地：{address} · 来源：{label}{accuracy}
    </span>
  );
}

// ── Main App ─────────────────────────────────────────────────────
const App: React.FC = () => {
  // Query
  const [query, setQuery] = useState(FAMILY_EXAMPLE);
  const [currentQuery, setCurrentQuery] = useState('');

  // Results
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PlanResponseV2 | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streamFailed, setStreamFailed] = useState(false);

  // Provider status
  const [pStatus, setPStatus] = useState<ProviderStatus | null>(null);
  const [pStatusV2, setPStatusV2] = useState<ProviderStatusV2 | null>(null);
  const [appMode, setAppMode] = useState('loading...');

  // Streaming state (always on by default)
  const [streamTrace, setStreamTrace] = useState<Array<{ phase: string; message: string }>>([]);
  const [streamToolCalls, setStreamToolCalls] = useState<ToolCall[]>([]);
  const [streamFallbacks, setStreamFallbacks] = useState<FallbackAction[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  // Location
  const [userLocation, setUserLocation] = useState<UserLocation | null>(null);
  const [locatingStatus, setLocatingStatus] = useState('');
  const [manualAddress, setManualAddress] = useState('');

  // Demo scenario
  const [demoScenario, setDemoScenario] = useState('normal');

  // Mode switch
  const [modeSwitching, setModeSwitching] = useState(false);
  const handleSwitchMode = async (newMode: string) => {
    setModeSwitching(true);
    try {
      const r = await switchAppMode(newMode);
      setAppMode(r.app_mode);
      setPStatus(r.providers);
      setPStatusV2(prev => prev ? { ...prev, app_mode: r.app_mode, providers: r.providers, safe_for_live_demo: r.safe_for_live_demo } : null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setModeSwitching(false);
    }
  };

  // Init
  useEffect(() => {
    getProviderStatus().then(s => { setPStatus(s.provider_status); setAppMode(s.app_mode); }).catch(() => {});
    getProviderStatusV2().then(s => setPStatusV2(s)).catch(() => {});
  }, []);

  // ── Browser Geolocation ──────────────────────────────────────
  const handleGetLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setLocatingStatus('浏览器不支持定位，使用默认地址');
      return;
    }
    setLocatingStatus('定位中...');
    navigator.geolocation.getCurrentPosition(
      pos => {
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy, source: 'browser_geolocation' });
        const m = Math.round(pos.coords.accuracy);
        setLocatingStatus(pos.coords.accuracy > 1000 ? `精度较低(~${m}m)，已结合默认地址` : `已定位 (精度约 ${m}m)`);
      },
      () => { setUserLocation(null); setLocatingStatus('定位失败，使用默认地址'); },
      { timeout: 8000, maximumAge: 300000 },
    );
  }, []);

  // ── Manual address ───────────────────────────────────────────
  const handleAddress = (addr: string) => {
    setManualAddress(addr);
    if (!addr) { setUserLocation(null); setLocatingStatus(''); return; }
    setUserLocation({ source: 'manual', address: addr });
    setLocatingStatus(`出发地: ${addr}`);
  };

  // ── Plan (stream-first with non-streaming fallback) ──────────
  const handlePlan = useCallback(async (q: string) => {
    if (abortRef.current) abortRef.current.abort();
    setLoading(true); setError(null); setCurrentQuery(q);
    setResult(null); setStreamTrace([]); setStreamToolCalls([]); setStreamFallbacks([]);
    setStreamFailed(false);

    // Try streaming first
    let streamErrored = false;
    abortRef.current = planQueryStream('u_001', q,
      (evt: SSEEvent) => {
        if (evt.type === 'trace' && evt.phase && evt.message) setStreamTrace(p => [...p, { phase: evt.phase!, message: evt.message! }]);
        if (evt.type === 'tool_call' && evt.tool_name) setStreamToolCalls(p => [...p, { tool_name: evt.tool_name, success: evt.status === 'success', message: evt.message || '', input: evt.input, output: evt.output }]);
        if (evt.type === 'fallback') setStreamFallbacks(p => [...p, { reason: evt.reason || '', action: evt.action || '', result: evt.result || '' }]);
        if (evt.type === 'final' && evt.data) setResult(evt.data as PlanResponseV2);
        if (evt.type === 'error') { setError(evt.message || 'Stream error'); streamErrored = true; }
      },
      () => {
        setLoading(false);
        // If stream completed but no result, try non-streaming fallback
        if (streamErrored && !result) {
          setStreamFailed(true);
          handlePlanFallback(q);
        }
      },
      err => {
        setError(err);
        setLoading(false);
        // Stream failed entirely, fallback to non-streaming
        setStreamFailed(true);
        handlePlanFallback(q);
      },
      userLocation, demoScenario,
    );
  }, [userLocation, demoScenario, result]);

  // Fallback to non-streaming request
  const handlePlanFallback = useCallback(async (q: string) => {
    setLoading(true);
    try {
      const res = await planQuery('u_001', q, userLocation, demoScenario);
      setResult(res);
      setError(e => e ? `${e} (已自动切换到普通模式)` : null);
    } catch (e: any) {
      setError(prev => `${prev || ''}\n普通模式也失败了: ${e.message}`.trim());
    } finally {
      setLoading(false);
    }
  }, [userLocation, demoScenario]);

  useEffect(() => () => { abortRef.current?.abort(); }, []);

  // ── Display data (stream data takes priority when streaming) ───
  const hasStreamData = streamTrace.length > 0 || streamToolCalls.length > 0;
  const displayTrace = hasStreamData ? streamTrace : (result?.planning_trace || []);
  const displayTools  = hasStreamData ? streamToolCalls : (result?.tool_calls || []);
  const displayFallbacks = (streamFallbacks.length > 0) ? streamFallbacks : (result?.fallback_actions || []);
  const displayCompleted = result?.completed_actions || [];
  const sanitizedSummary = result?.summary ? sanitizeText(result.summary) : '';
  const sanitizedExplanation = result?.explanation ? sanitizeText(result.explanation) : '';

  // ── Render ───────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#f8fafc]">
      {/* ═══ Header ═══ */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🏠</span>
            <div>
              <h1 className="text-base font-bold text-gray-900 tracking-tight">Local Life Agent</h1>
              <p className="text-[11px] text-gray-400">一句话安排你的本地休闲活动</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Mode switcher */}
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => handleSwitchMode('demo_real')}
                disabled={modeSwitching}
                className={`text-[11px] px-2.5 py-1 rounded-md font-medium transition-all ${
                  appMode === 'demo_real' || appMode === 'demo'
                    ? 'bg-white text-emerald-700 shadow-sm'
                    : 'text-gray-400 hover:text-gray-600'
                }`}
              >真实</button>
              <button
                onClick={() => handleSwitchMode('demo_safe')}
                disabled={modeSwitching}
                className={`text-[11px] px-2.5 py-1 rounded-md font-medium transition-all ${
                  appMode === 'demo_safe'
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-gray-400 hover:text-gray-600'
                }`}
              >稳定</button>
            </div>
            {modeSwitching && <span className="text-[10px] text-gray-400">切换中...</span>}
            {pStatusV2?.safe_for_live_demo && <span className="chip bg-blue-50 text-blue-600">离线安全</span>}

            <span className="text-gray-200">|</span>

            {/* Provider chips */}
            <ProviderChip label="LLM" value={pStatus?.llm} />
            <ProviderChip label="POI" value={pStatus?.poi} />
            <ProviderChip label="天气" value={pStatus?.weather} />
            <ProviderChip label="路线" value={pStatus?.route} />
            <span className="chip chip-off">执行:mock</span>
          </div>
        </div>
      </header>

      {/* ═══ Main ═══ */}
      <main className="max-w-6xl mx-auto px-5 py-6 space-y-5">
        {/* ── Query Card ── */}
        <div className="card">
          <textarea
            className="w-full h-20 p-3 border border-gray-200 rounded-lg text-sm resize-none
                       focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400
                       placeholder:text-gray-300"
            value={query} onChange={e => setQuery(e.target.value)}
            placeholder="描述你的下午活动需求，例如：下午带孩子去公园玩，想吃川菜..."
          />

          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <button onClick={() => handlePlan(query)} disabled={loading || !query.trim()} className="btn btn-primary">
              {loading ? (
                <><svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>规划中...</>
              ) : '开始规划'}
            </button>

            <button onClick={() => setQuery(FAMILY_EXAMPLE)} className="btn btn-secondary">家庭示例</button>
            <button onClick={() => setQuery(FRIENDS_EXAMPLE)} className="btn btn-secondary">朋友示例</button>

            <span className="text-gray-200 mx-1">|</span>

            {/* Location */}
            <button onClick={handleGetLocation} className="btn btn-secondary">定位</button>
            <select value={manualAddress} onChange={e => handleAddress(e.target.value)} className="select-sm">
              {ADDRESS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            {locatingStatus && <span className="text-[11px] text-gray-400 truncate max-w-[180px]">{locatingStatus}</span>}

            {/* Demo scenario */}
            <div className="ml-auto flex items-center gap-1.5">
              <span className="text-[11px] text-gray-400">场景:</span>
              <select value={demoScenario} onChange={e => setDemoScenario(e.target.value)} className="select-sm" title={SCENARIO_OPTIONS.find(s => s[0] === demoScenario)?.[2]}>
                {SCENARIO_OPTIONS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
              </select>
            </div>
          </div>

          {currentQuery && <p className="text-[11px] text-gray-400 mt-2 truncate">当前查询: {currentQuery}</p>}
        </div>

        {/* ── Error ── */}
        {error && (
          <div className="card !border-red-200 !bg-red-50">
            <p className="text-sm text-red-700 flex items-center gap-2"><span>❌</span> {error}</p>
          </div>
        )}

        {/* ── Streaming in-progress ── */}
        {loading && !result && (
          <div className="card flex items-center gap-3">
            <span className="flex gap-1"><span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:0ms]"/><span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:150ms]"/><span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:300ms]"/></span>
            <span className="text-sm text-blue-600 font-medium">Agent 正在实时规划...</span>
          </div>
        )}

        {/* ═══ Results ═══ */}
        {(result || (hasStreamData)) && (
          <>
            {/* Status bar */}
            {result && (
              <div className="card flex items-center gap-3 flex-wrap !py-3">
                <span className={`badge text-sm ${result.status === 'success' ? 'badge-green' : result.status === 'partial' ? 'badge-yellow' : 'badge-red'}`}>
                  {result.status === 'success' ? '全部成功' : result.status === 'partial' ? '部分完成' : '失败'}
                </span>
                <span className="badge badge-blue">
                  {result.scene === 'family' ? '家庭' : result.scene === 'friends' ? '朋友' : result.scene === 'couple' ? '约会' : result.scene || '个人'}
                </span>
                {/* Location display */}
                <LocationSourceLabel loc={result.origin_location} />
                {demoScenario !== 'normal' && (
                  <span className="badge bg-orange-50 text-orange-700 border-orange-200">
                    {SCENARIO_OPTIONS.find(s => s[0] === demoScenario)?.[1] || demoScenario}
                  </span>
                )}
                <span className="text-[11px] text-gray-400 ml-auto">
                  {result.total_time_min ? `预计 ${result.total_time_min} 分钟` : ''}
                  {result.parsed_intent?.confidence ? ` · 置信度 ${(result.parsed_intent.confidence * 100).toFixed(0)}%` : ''}
                </span>
              </div>
            )}

            {/* Stream-failed fallback notice */}
            {streamFailed && result && (
              <div className="card !border-yellow-200 !bg-yellow-50">
                <p className="text-xs text-yellow-700">流式连接失败，已自动切换到普通模式展示结果。</p>
              </div>
            )}

            {/* 3-column grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              {/* Left */}
              <div className="lg:col-span-1 space-y-4">
                <AgentTracePanel trace={displayTrace} />
                <ToolCallTimeline toolCalls={displayTools} />
              </div>

              {/* Center */}
              <div className="lg:col-span-1 space-y-4">
                {sanitizedSummary && (
                  <div className="card">
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">推荐方案</h3>
                    <p className="text-sm text-gray-600 whitespace-pre-line leading-relaxed">{sanitizedSummary}</p>
                  </div>
                )}
                {result?.share_message && <ShareMessageBox message={sanitizeText(result.share_message)} />}
              </div>

              {/* Right */}
              <div className="lg:col-span-1 space-y-4">
                <OrderResultCard completedActions={displayCompleted} fallbackActions={displayFallbacks} />
                {result?.itinerary && result.itinerary.length > 0 && (
                  <div className="card">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">行程</h3>
                    <div className="space-y-1.5">
                      {result.itinerary.map((item, i) => (
                        <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-50/70">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                            item.type === 'travel' ? 'bg-blue-100 text-blue-600' :
                            item.type === 'activity' ? 'bg-emerald-100 text-emerald-600' :
                            item.type === 'meal' ? 'bg-orange-100 text-orange-600' :
                            'bg-gray-200 text-gray-500'
                          }`}>{item.type}</span>
                          <span className="text-sm text-gray-800 flex-1">{item.title}</span>
                          {item.time && <span className="text-[11px] text-gray-400">{item.time}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Score Table */}
            {result && (result.rankings?.poi_rankings?.length > 0 || result.rankings?.restaurant_rankings?.length > 0) && (
              <div className="card">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">评分分解</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-gray-400 border-b">
                      <th className="pb-2 pr-3 font-medium">候选</th><th className="pb-2 pr-3 font-medium">距离</th><th className="pb-2 pr-3 font-medium">路线</th>
                      <th className="pb-2 pr-3 font-medium">预算</th><th className="pb-2 pr-3 font-medium">场景</th><th className="pb-2 pr-3 font-medium">天气</th>
                      <th className="pb-2 pr-3 font-medium">偏好</th><th className="pb-2 pr-3 font-medium text-orange-400">未知扣分</th><th className="pb-2 font-semibold">总分</th>
                    </tr></thead>
                    <tbody>
                      {(result.rankings?.poi_rankings || []).map((r, i) => (
                        <tr key={`p${i}`} className={i === 0 ? 'bg-blue-50/50' : ''}>
                          <td className="py-1.5 pr-3 font-medium">{r.candidate_name}{i === 0 ? ' TOP' : ''}</td>
                          <td className="py-1.5 pr-3">{r.distance_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.route_time_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.budget_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.scene_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.weather_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.preference_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3 text-orange-400">-{r.unknown_penalty.toFixed(2)}</td>
                          <td className="py-1.5 font-semibold">{r.final_score.toFixed(2)}</td>
                        </tr>
                      ))}
                      {(result.rankings?.restaurant_rankings || []).map((r, i) => (
                        <tr key={`r${i}`} className={i === 0 ? 'bg-blue-50/50' : ''}>
                          <td className="py-1.5 pr-3 font-medium">{r.candidate_name}{i === 0 ? ' TOP' : ''}</td>
                          <td className="py-1.5 pr-3">{r.distance_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.route_time_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.budget_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.scene_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.weather_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3">{r.preference_score.toFixed(2)}</td>
                          <td className="py-1.5 pr-3 text-orange-400">-{r.unknown_penalty.toFixed(2)}</td>
                          <td className="py-1.5 font-semibold">{r.final_score.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Weather + Top Picks */}
            {result && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div className="card">
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">天气</h3>
                  {result.weather ? (
                    <p className="text-sm">{result.weather.city}: <strong>{result.weather.day_weather}</strong> {result.weather.day_temp}°C / {result.weather.night_temp}°C</p>
                  ) : <p className="text-xs text-gray-400">无数据</p>}
                </div>
                <div className="card">
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Top Picks</h3>
                  {result.top_picks?.poi && <p className="text-sm">活动: <strong>{result.top_picks.poi.name}</strong> {result.top_picks.poi_score && <span className="text-xs text-gray-400">({result.top_picks.poi_score.final_score.toFixed(2)})</span>}</p>}
                  {result.top_picks?.restaurant && <p className="text-sm">餐厅: <strong>{result.top_picks.restaurant.name}</strong> {result.top_picks.restaurant_score && <span className="text-xs text-gray-400">({result.top_picks.restaurant_score.final_score.toFixed(2)})</span>}</p>}
                </div>
              </div>
            )}

            {/* Debug (collapsible) */}
            {result?.debug && (
              <details className="card !py-3">
                <summary className="text-xs font-medium text-gray-500 cursor-pointer select-none">Debug · feasibility={result.debug.feasibility?.feasible ? 'OK' : 'FAIL'} · actions={result.debug.action_plan?.length || 0} · scenario={result.debug.demo_scenario || 'normal'}</summary>
                <div className="mt-2 text-[11px] text-gray-500 space-y-1 max-h-40 overflow-y-auto">
                  {(result.debug.feasibility?.checks || []).map((c, i) => (
                    <p key={i}>[{c.result}] {c.check}: {c.detail}</p>
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      </main>
    </div>
  );
};

export default App;
