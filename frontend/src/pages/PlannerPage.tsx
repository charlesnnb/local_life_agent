import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  confirmReplan,
  createPlan,
  createPlanStream,
  getCurrentPreferences,
  PlanEvent,
  PlanResponse,
  ReplanProposal,
  RuntimeMode,
  UserPreference,
} from '../api';
import AgentProgress from '../components/AgentProgress';
import ExceptionConfirmationCard from '../components/ExceptionConfirmationCard';
import ExecutionActions from '../components/ExecutionActions';
import PlanSummary from '../components/PlanSummary';
import PlanningInput, { DEMO_SCENARIOS } from '../components/PlanningInput';
import ShareMessage from '../components/ShareMessage';
import Timeline from '../components/Timeline';


export default function PlannerPage({
  runtime,
}: {
  runtime: RuntimeMode;
}) {
  const [query, setQuery] = useState<string>(DEMO_SCENARIOS[0].query);
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [progressEvents, setProgressEvents] = useState<PlanEvent[]>([]);
  const [preference, setPreference] = useState<UserPreference | null>(null);
  const [showPreferencePrompt, setShowPreferencePrompt] = useState(false);
  const [confirmingProposalId, setConfirmingProposalId] = useState('');
  const [actionsConfirmed, setActionsConfirmed] = useState(false);

  useEffect(() => {
    getCurrentPreferences()
      .then(profile => setPreference(profile.preference))
      .catch(() => setPreference(null));
    setShowPreferencePrompt(
      localStorage.getItem('preference-questionnaire-completed') !== 'true'
      && sessionStorage.getItem('preference-prompt-dismissed') !== 'true',
    );
  }, []);

  const dismissPreferencePrompt = () => {
    sessionStorage.setItem('preference-prompt-dismissed', 'true');
    setShowPreferencePrompt(false);
  };

  const submit = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    setProgressEvents([]);
    setActionsConfirmed(false);
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

  const confirmProposal = async (
    proposal: ReplanProposal,
    optionId: string,
  ) => {
    if (!result) return;
    setConfirmingProposalId(proposal.proposal_id);
    setError('');
    try {
      setResult(await confirmReplan(result, proposal.proposal_id, optionId));
      setActionsConfirmed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新计划失败');
    } finally {
      setConfirmingProposalId('');
    }
  };

  const messageAction = result?.actions.find(
    action => action.type === 'send_message',
  );
  const shareMessage = result?.composition?.share_message
    || messageAction?.message
    || '';

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      {showPreferencePrompt && (
        <section className="flex flex-col gap-4 rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-bold text-blue-950">
              用 1 分钟告诉 Agent 你的偏好
            </h2>
            <p className="mt-1 text-sm text-blue-700">
              可提升活动、餐厅、通勤和排队时间的推荐匹配度。
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              to="/settings"
              className="inline-flex min-h-10 items-center rounded-xl bg-blue-600 px-4 text-sm font-bold text-white"
            >
              开始设置
            </Link>
            <button
              type="button"
              onClick={dismissPreferencePrompt}
              className="min-h-10 rounded-xl border border-blue-200 bg-white px-4 text-sm font-bold text-blue-700"
            >
              稍后再说
            </button>
          </div>
        </section>
      )}

      <PlanningInput
        query={query}
        onQueryChange={setQuery}
        onSubmit={submit}
        loading={loading}
        error={error}
        preference={preference}
      />

      {loading && progressEvents.length > 0 && (
        <AgentProgress events={progressEvents} loading />
      )}

      {result && (
        <>
          <PlanSummary result={result} />

          {result.replan_proposals.map(proposal => (
            <ExceptionConfirmationCard
              key={proposal.proposal_id}
              proposal={proposal}
              busy={confirmingProposalId === proposal.proposal_id}
              onConfirm={optionId => confirmProposal(proposal, optionId)}
            />
          ))}

          {result.planning_warnings.length > 0 && (
            <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5 sm:p-6">
              <h3 className="font-bold text-amber-950">行程提醒</h3>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-900">
                {result.planning_warnings.map(warning => (
                  <li key={warning}>- {warning}</li>
                ))}
              </ul>
            </section>
          )}

          <Timeline route={result.route} timeline={result.timeline} />

          <section className="grid gap-6 lg:grid-cols-2">
            <ExecutionActions
              actions={result.actions}
              confirmed={actionsConfirmed}
              onConfirm={() => setActionsConfirmed(true)}
            />
            {shareMessage && (
              <ShareMessage
                message={shareMessage}
                personal={messageAction?.target === '自己'}
              />
            )}
          </section>

          <details className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <summary className="cursor-pointer list-none px-5 py-4 text-sm font-bold text-slate-700 sm:px-6">
              查看推荐依据与任务详情
            </summary>
            <div className="grid gap-6 border-t border-slate-100 px-5 py-5 sm:px-6 lg:grid-cols-2">
              <div>
                <h3 className="font-bold text-slate-900">偏好与选择依据</h3>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  {result.preference_explanation.map(item => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
                {result.decision_explanation && (
                  <p className="mt-4 rounded-xl bg-blue-50 p-4 text-sm leading-6 text-blue-800">
                    {result.decision_explanation.public_reasoning}
                  </p>
                )}
              </div>
              {result.task_plan && (
                <div>
                  <h3 className="font-bold text-slate-900">识别出的任务顺序</h3>
                  <ol className="mt-3 space-y-3">
                    {result.task_plan.tasks.map((task, index) => (
                      <li
                        key={task.task_id}
                        className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm"
                      >
                        <p className="font-bold text-slate-800">
                          {index + 1}. {task.description}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {task.time_window} · {task.route_needed
                            ? '加入线下路线'
                            : '不进入线下路线'}
                        </p>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          </details>

          {progressEvents.length > 0 && !loading && (
            <AgentProgress events={progressEvents} loading={false} />
          )}

          <SourceSummary
            runtime={runtime}
            result={result}
            events={progressEvents}
          />
        </>
      )}
    </main>
  );
}


function SourceSummary({
  runtime,
  result,
  events,
}: {
  runtime: RuntimeMode;
  result: PlanResponse;
  events: PlanEvent[];
}) {
  const llmFellBack = runtime.llm === 'deepseek' && events.some(event => (
    event.stage === 'api_fallback_triggered'
    && /DeepSeek|LLM/i.test(event.message)
  ));
  const taskSource = runtime.llm === 'deepseek'
    ? llmFellBack ? 'Rule fallback' : 'DeepSeek'
    : 'Rule/Mock';
  const routeSource = result.route.source === 'amap'
    ? 'AMap'
    : result.route.source === 'mixed'
      ? 'AMap + Mock fallback'
      : runtime.amap === 'amap' ? 'Mock fallback' : 'Mock';
  const mapSource = import.meta.env.VITE_AMAP_JS_KEY?.trim()
    ? 'AMap JS API'
    : '离线路线图';
  const actionSource = runtime.actions === 'mock_fallback'
    ? 'Mock fallback'
    : runtime.actions === 'live' ? 'Live' : 'Mock';
  return (
    <section className="rounded-2xl border border-slate-200 bg-slate-100/70 px-5 py-4 text-xs leading-6 text-slate-500">
      <span className="font-bold text-slate-700">本次数据来源：</span>
      任务理解 {taskSource} · 地点与路线 {routeSource} ·
      地图 {mapSource} · 点餐/预约/消息 {actionSource}
    </section>
  );
}
