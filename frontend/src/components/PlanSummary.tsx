import type { PlanResponse } from '../api';


function durationText(minutes: number): string {
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.round(minutes / 6) / 10;
  return `${hours} 小时`;
}


export default function PlanSummary({ result }: { result: PlanResponse }) {
  const detailSummary = result.composition?.summary === result.plan.summary
    ? ''
    : result.composition?.summary || (
      result.natural_language === result.plan.summary ? '' : result.natural_language
    );
  const timeWindows = result.user_intent.time_windows.length > 0
    ? result.user_intent.time_windows
    : [result.user_intent.time_window];
  const tags = [
    ...timeWindows,
    ...result.user_intent.activity_preferences,
    ...result.user_intent.diet_preferences,
    ...result.user_intent.avoid,
  ].filter((value, index, values) => value && values.indexOf(value) === index);

  return (
    <section className="overflow-hidden rounded-3xl border border-blue-200 bg-white shadow-sm">
      <div className="bg-blue-600 px-5 py-6 text-white sm:px-8">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-100">
          Your plan is ready
        </p>
        <h2 className="mt-2 text-2xl font-bold sm:text-3xl">
          {result.plan.summary}
        </h2>
        {detailSummary && (
          <p className="mt-3 max-w-3xl text-sm leading-7 text-blue-50">
            {detailSummary}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 divide-x divide-y divide-slate-100 sm:grid-cols-4 sm:divide-y-0">
        <Metric label="时间范围" value={timeWindows.join(' · ')} />
        <Metric
          label="总时长"
          value={durationText(result.timeline.total_duration_minutes)}
        />
        <Metric
          label="总通勤"
          value={`${result.route.total_travel_minutes} 分钟`}
        />
        <Metric
          label="线下地点"
          value={`${result.route.stops.length} 个`}
        />
      </div>

      {(tags.length > 0 || result.plan.reasons.length > 0) && (
        <div className="border-t border-slate-100 px-5 py-5 sm:px-8">
          <div className="flex flex-wrap gap-2">
            {tags.slice(0, 6).map(tag => (
              <span
                key={tag}
                className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600"
              >
                {tag}
              </span>
            ))}
          </div>
          {result.plan.reasons[0] && (
            <p className="mt-4 text-sm leading-6 text-slate-600">
              <span className="font-bold text-slate-800">推荐理由：</span>
              {result.plan.reasons.slice(0, 2).join('；')}
            </p>
          )}
        </div>
      )}
    </section>
  );
}


function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 px-4 py-4 sm:px-6">
      <p className="text-xs font-semibold text-slate-400">{label}</p>
      <p className="mt-1 truncate text-base font-bold text-slate-900">{value}</p>
    </div>
  );
}
