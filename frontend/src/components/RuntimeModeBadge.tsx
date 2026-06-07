import type { PlanResponse, RuntimeMode } from '../api';


interface RuntimeModeBadgeProps {
  runtime: RuntimeMode;
  result: PlanResponse | null;
  compact?: boolean;
}


const LABELS = {
  llm: {
    mock: 'Mock LLM',
    deepseek: 'DeepSeek',
  },
  amap: {
    mock: 'Mock AMap',
    amap: 'AMap',
  },
  actions: {
    mock: 'Mock Actions',
    mock_fallback: 'Mock fallback',
    live: 'Live Actions',
  },
} as const;

const MODE_LABELS: Record<RuntimeMode['mode'], string> = {
  demo: 'Demo Mode',
  hybrid: 'Hybrid Live Mode',
  live: 'Live Mode',
};

const MODE_STYLES: Record<RuntimeMode['mode'], string> = {
  demo: 'bg-amber-100 text-amber-900',
  hybrid: 'bg-blue-100 text-blue-800',
  live: 'bg-emerald-100 text-emerald-900',
};


export default function RuntimeModeBadge({
  runtime,
  result,
  compact = false,
}: RuntimeModeBadgeProps) {
  const planSource = result
    ? result.route.source === 'amap'
      ? 'AMap'
      : result.route.source === 'mixed'
        ? 'AMap + Mock'
        : 'Mock'
    : null;

  return (
    <div
      aria-label="当前运行模式"
      className={`${compact ? '' : 'mt-4'} flex flex-wrap items-center gap-2`}
    >
      <span
        className={`rounded-full px-3 py-1 text-xs font-bold ${MODE_STYLES[runtime.mode]}`}
      >
        {MODE_LABELS[runtime.mode]}
      </span>
      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
        {LABELS.llm[runtime.llm]}
      </span>
      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
        {LABELS.amap[runtime.amap]}
      </span>
      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
        {LABELS.actions[runtime.actions]}
      </span>
      {planSource && (
        <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
          本次地点/路线：{planSource}
        </span>
      )}
    </div>
  );
}
