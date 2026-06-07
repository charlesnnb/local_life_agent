import type { UserPreference } from '../api';
import PreferenceSummary from './PreferenceSummary';


export const DEMO_SCENARIOS = [
  {
    label: '家庭亲子',
    query: '今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥',
  },
  {
    label: '朋友多人',
    query: '今天下午我们4个人，2男2女，想出去玩几个小时，顺便吃饭，别太远，最好能聊天拍照',
  },
  {
    label: '多阶段一天',
    query: '今天早上想去公园玩，然后中午点个外卖吃肯德基，下午去打台球，晚上去喝茶，夜宵吃个螺蛳粉',
  },
  {
    label: '天气室内',
    query: '周末可能下雨，想带孩子出去玩，最好室内，不想排队太久，晚上吃清淡一点',
  },
  {
    label: '预约失败/备选',
    query: '今天下午想去展览，晚上吃火锅，最好提前预约，别排队',
  },
] as const;


interface PlanningInputProps {
  query: string;
  onQueryChange: (query: string) => void;
  onSubmit: () => void;
  loading: boolean;
  error: string;
  preference: UserPreference | null;
}


export default function PlanningInput({
  query,
  onQueryChange,
  onSubmit,
  loading,
  error,
  preference,
}: PlanningInputProps) {
  return (
    <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-5 py-6 sm:px-8 sm:py-8">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600">
          Plan your day
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
          一句话，把今天安排好
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500 sm:text-base">
          告诉我时间、同行人和想做的事，我会帮你生成可执行路线。
        </p>
      </div>

      <div className="px-5 py-5 sm:px-8 sm:py-6">
        <label className="text-sm font-bold text-slate-800" htmlFor="query">
          你的周末或闲时需求
        </label>
        <textarea
          id="query"
          value={query}
          onChange={event => onQueryChange(event.target.value)}
          className="mt-3 min-h-32 w-full resize-y rounded-2xl border border-slate-200 bg-slate-50/60 p-4 text-[15px] leading-7 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-100"
          placeholder="例如：今天下午带孩子去室内玩，晚上吃清淡一点，别太远。"
        />

        <div className="mt-4 flex flex-wrap gap-2">
          {DEMO_SCENARIOS.map(scenario => (
            <button
              key={scenario.label}
              type="button"
              onClick={() => onQueryChange(scenario.query)}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
            >
              {scenario.label}
            </button>
          ))}
        </div>

        <div className="mt-5 flex flex-col gap-4 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <PreferenceSummary preference={preference} />
          <button
            type="button"
            onClick={onSubmit}
            disabled={loading || !query.trim()}
            className="inline-flex min-h-12 items-center justify-center rounded-xl bg-blue-600 px-6 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? '正在生成可执行计划...' : '开始规划'}
          </button>
        </div>
        {error && (
          <p className="mt-3 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </p>
        )}
      </div>
    </section>
  );
}
