import { PlanEvent } from '../api';


interface AgentProgressProps {
  events: PlanEvent[];
  loading: boolean;
}

const SOURCE_LABELS: Record<PlanEvent['source'], string> = {
  system: 'Agent',
  deepseek: 'DeepSeek',
  amap: 'AMap',
  mock: 'Mock fallback',
};

const SOURCE_STYLES: Record<PlanEvent['source'], string> = {
  system: 'bg-slate-100 text-slate-600',
  deepseek: 'bg-violet-100 text-violet-700',
  amap: 'bg-blue-100 text-blue-700',
  mock: 'bg-amber-100 text-amber-700',
};


function AgentProgress({ events, loading }: AgentProgressProps) {
  return (
    <section className="rounded-2xl border border-blue-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <h2 className="font-bold text-slate-900">Agent 执行过程</h2>
        <span className="text-xs font-medium text-blue-600">
          {loading ? '处理中' : '已完成'}
        </span>
      </div>

      <ol className="mt-4 space-y-3">
        {events.map((event, index) => {
          const isLatest = loading && index === events.length - 1;
          return (
            <li
              key={`${event.stage}-${index}`}
              className="flex items-start gap-3 text-sm text-slate-600"
            >
              <span
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white ${
                  isLatest ? 'animate-pulse bg-blue-500' : 'bg-emerald-500'
                }`}
              >
                {index + 1}
              </span>
              <span className="min-w-0">
                <span
                  className={`mr-2 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${SOURCE_STYLES[event.source]}`}
                >
                  {SOURCE_LABELS[event.source]}
                </span>
                <span className={isLatest ? 'font-medium text-blue-700' : ''}>
                  {event.message}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}


export default AgentProgress;
