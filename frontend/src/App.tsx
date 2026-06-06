import { useState } from 'react';

import {
  createPlan,
  createPlanStream,
  PlanEvent,
  PlanResponse,
} from './api';
import AgentProgress from './components/AgentProgress';
import PreferenceSetup from './components/PreferenceSetup';
import Timeline from './components/Timeline';


const EXAMPLE =
  '今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥';


function App() {
  const [query, setQuery] = useState(EXAMPLE);
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [progressEvents, setProgressEvents] = useState<PlanEvent[]>([]);

  const submit = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    setProgressEvents([]);
    try {
      const streamedResult = await createPlanStream(query.trim(), event => {
        if (event.type === 'progress') {
          setProgressEvents(current => [...current, event]);
        }
      });
      setResult(streamedResult);
    } catch {
      setProgressEvents(current => [
        ...current,
        {
          type: 'progress',
          stage: 'fallback',
          message: '流式连接不可用，已切换普通规划模式',
          data: {},
          source: 'mock',
        },
      ]);
      try {
        setResult(await createPlan(query.trim()));
      } catch (err) {
        setError(err instanceof Error ? err.message : '规划失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const shareMessage = result?.actions.find(
    action => action.type === 'send_message',
  )?.message;
  const shareTarget = result?.actions.find(
    action => action.type === 'send_message',
  )?.target;
  const durationLabel = result
    ? result.user_intent.duration_hours[0] === result.user_intent.duration_hours[1]
      ? `${result.user_intent.duration_hours[0]}小时`
      : `${result.user_intent.duration_hours[0]}-${result.user_intent.duration_hours[1]}小时`
    : '';

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-6 py-5">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-600">
            Local Life Agent
          </p>
          <h1 className="mt-1 text-2xl font-bold">一句话，把下午安排好</h1>
          <p className="mt-1 text-sm text-slate-500">
            先理解你要做的每件事，再逐项调用工具并组成完整行程。
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        <PreferenceSetup />

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <label className="text-sm font-semibold" htmlFor="query">
            你的周末或闲时需求
          </label>
          <textarea
            id="query"
            value={query}
            onChange={event => setQuery(event.target.value)}
            className="mt-3 h-28 w-full resize-none rounded-xl border border-slate-200 p-4 text-sm leading-6 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          />
          <button
            type="button"
            onClick={submit}
            disabled={loading || !query.trim()}
            className="mt-4 rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? '正在生成可执行计划...' : '开始规划'}
          </button>
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        </section>

        {progressEvents.length > 0 && (
          <AgentProgress events={progressEvents} loading={loading} />
        )}

        {result && (
          <>
            <section className="rounded-2xl bg-slate-900 p-6 text-white shadow-sm">
              <p className="text-sm text-blue-200">已完成规划</p>
              <h2 className="mt-1 text-2xl font-bold">{result.plan.summary}</h2>
              <div className="mt-4 flex flex-wrap gap-2">
                {[
                  ...(result.user_intent.time_windows.length > 0
                    ? result.user_intent.time_windows
                    : [result.user_intent.time_window]),
                  durationLabel,
                  ...result.user_intent.activity_preferences,
                  ...result.user_intent.diet_preferences,
                ].map(item => (
                  <span key={item} className="rounded-full bg-white/10 px-3 py-1 text-xs">
                    {item}
                  </span>
                ))}
              </div>
            </section>

            {result.task_plan && result.task_plan.tasks.length > 0 && (
              <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
                  Ordered Tasks
                </p>
                <h3 className="mt-1 text-lg font-bold">识别出的任务顺序</h3>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {result.task_plan.tasks.map((task, index) => (
                    <div
                      key={task.task_id}
                      className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                    >
                      <p className="text-xs font-semibold text-blue-600">
                        {index + 1}. {task.time_window} · {task.tool_name}
                      </p>
                      <p className="mt-1 font-semibold">{task.description}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {task.route_needed ? '需要加入路线' : '不进入线下路线'}
                        {task.search_query ? ` · 搜索：${task.search_query}` : ''}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {result.planning_warnings.length > 0 && (
              <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
                <h3 className="font-bold text-amber-950">时间与体力提醒</h3>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-900">
                  {result.planning_warnings.map(warning => (
                    <li key={warning}>- {warning}</li>
                  ))}
                </ul>
              </section>
            )}

            <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
              <Timeline route={result.route} timeline={result.timeline} />

              <div className="space-y-6">
                <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h3 className="font-bold">推荐理由</h3>
                  <ul className="mt-3 space-y-2 text-sm text-slate-600">
                    {result.plan.reasons.map(reason => (
                      <li key={reason}>- {reason}</li>
                    ))}
                  </ul>
                </section>

                <section className="rounded-2xl border border-violet-200 bg-violet-50 p-6">
                  <h3 className="font-bold text-violet-950">偏好如何影响推荐</h3>
                  <ul className="mt-3 space-y-2 text-sm text-violet-800">
                    {result.preference_explanation.map(item => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                </section>

                {result.decision_explanation && (
                  <section className="rounded-2xl border border-blue-200 bg-blue-50 p-6">
                    <h3 className="font-bold text-blue-950">Agent 选择依据</h3>
                    <p className="mt-2 text-sm leading-6 text-blue-800">
                      {result.decision_explanation.public_reasoning}
                    </p>
                  </section>
                )}

                <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h3 className="font-bold">已模拟执行</h3>
                  <div className="mt-3 space-y-3">
                    {result.actions.map(action => (
                      <div
                        key={`${action.type}-${action.target}`}
                        className="rounded-xl bg-emerald-50 p-3"
                      >
                        <p className="text-sm font-semibold text-emerald-800">
                          {action.type === 'reservation'
                            ? '餐厅预约'
                            : action.type === 'food_order'
                              ? '外卖点餐'
                              : '计划消息'} · 成功
                        </p>
                        <p className="mt-1 text-xs text-emerald-700">
                          {action.type === 'send_message'
                            ? action.target === '自己'
                              ? '已生成个人计划备忘'
                              : `发送给 ${action.target}`
                            : action.message}
                        </p>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </section>

            {shareMessage && (
              <section className="rounded-2xl border border-blue-200 bg-blue-50 p-6">
                <p className="text-sm font-semibold text-blue-900">
                  {shareTarget === '自己' ? '个人计划备忘' : '可直接发送的计划消息'}
                </p>
                <p className="mt-3 leading-7 text-blue-950">{shareMessage}</p>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;
