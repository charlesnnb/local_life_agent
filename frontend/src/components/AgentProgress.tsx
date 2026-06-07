import { useMemo, useState } from 'react';

import type { PlanEvent } from '../api';


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


function formatMessage(event: PlanEvent) {
  if (event.source === 'deepseek') {
    return event.message
      .replace(/^正在用\s*DeepSeek\s*/i, '正在')
      .replace(/^DeepSeek\s*[：:]?\s*/i, '');
  }
  if (event.source === 'amap') {
    return event.message
      .replace(/^正在调用\s*(?:AMap|高德)\s*/i, '正在')
      .replace(/^(?:AMap|高德)\s*[：:]?\s*/i, '');
  }
  return event.message;
}


export default function AgentProgress({
  events,
  loading,
}: AgentProgressProps) {
  const [expanded, setExpanded] = useState(false);
  const displayEvents = useMemo(() => deduplicateAdjacentEvents(events), [events]);
  const toolCount = useMemo(() => {
    const tools = new Set<string>();
    displayEvents.forEach(event => {
      const toolName = event.data.tool_name;
      if (typeof toolName === 'string' && toolName) {
        tools.add(toolName);
      } else if (event.stage.includes('tool_')) {
        tools.add(event.stage);
      }
    });
    return tools.size;
  }, [displayEvents]);
  const latest = displayEvents[displayEvents.length - 1];
  const progressSummary = toolCount > 0
    ? `调用 ${toolCount} 个工具 · 共 ${displayEvents.length} 个步骤`
    : `共完成 ${displayEvents.length} 个规划步骤`;

  if (loading) {
    return (
      <section className="rounded-2xl border border-blue-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex items-start gap-4">
          <span className="mt-1 h-3 w-3 shrink-0 animate-pulse rounded-full bg-blue-600 ring-4 ring-blue-100" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-bold text-slate-950">
                正在为你安排今天的计划...
              </h2>
              <span className="text-xs font-semibold text-blue-600">
                已完成 {displayEvents.length} 个步骤
              </span>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-blue-600 transition-all"
                style={{ width: `${Math.min(92, 18 + displayEvents.length * 9)}%` }}
              />
            </div>
            {latest && (
              <p className="mt-3 text-sm font-medium text-slate-600">
                {formatMessage(latest)}
              </p>
            )}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <h2 className="font-bold text-slate-950">Agent 已完成规划</h2>
          <p className="mt-1 text-xs text-slate-500">
            {progressSummary}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(current => !current)}
          aria-expanded={expanded}
          className="min-h-10 rounded-xl border border-slate-200 bg-white px-4 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
        >
          {expanded ? '收起执行过程' : '查看执行过程'}
        </button>
      </div>

      {expanded && (
        <div className="border-t border-slate-100 px-5 py-5 sm:px-6">
          <ol className="space-y-4">
            {displayEvents.map((event, index) => (
              <EventRow
                key={`${event.stage}-${index}`}
                event={event}
                index={index}
              />
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}


function deduplicateAdjacentEvents(events: PlanEvent[]): PlanEvent[] {
  return events.filter((event, index) => {
    const previous = events[index - 1];
    return !previous
      || previous.stage !== event.stage
      || previous.message !== event.message;
  });
}


function EventRow({
  event,
  index,
}: {
  event: PlanEvent;
  index: number;
}) {
  const rejectedCandidates = Array.isArray(event.data.rejected_candidates)
    ? event.data.rejected_candidates.filter(
        (item): item is { name?: string; reason?: string } =>
          typeof item === 'object' && item !== null,
      )
    : [];
  const selectedResult =
    typeof event.data.selected_result === 'object'
    && event.data.selected_result !== null
      ? event.data.selected_result as {
          name?: string;
          selection_reasons?: unknown;
        }
      : null;
  const selectionReasons = Array.isArray(selectedResult?.selection_reasons)
    ? selectedResult.selection_reasons.filter(
        (reason): reason is string => typeof reason === 'string',
      )
    : [];
  const hasTechnicalDetails = rejectedCandidates.length > 0
    || event.source !== 'system'
    || Object.keys(event.data).length > 0;

  return (
    <li className="flex gap-3 text-sm text-slate-600">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-[11px] font-bold text-white">
        {index + 1}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-slate-700">{formatMessage(event)}</p>
        {selectedResult && (
          <div className="mt-2 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-800">
            <p className="font-bold">
              已选择：{selectedResult.name ?? '最佳候选'}
            </p>
            {selectionReasons.length > 0 && (
              <p className="mt-1">{selectionReasons.join('；')}</p>
            )}
          </div>
        )}
        {hasTechnicalDetails && (
          <details className="mt-2 text-xs text-slate-500">
            <summary className="cursor-pointer font-semibold text-slate-500 hover:text-slate-700">
              查看技术详情
            </summary>
            <div className="mt-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
              <span
                className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${SOURCE_STYLES[event.source]}`}
              >
                Provider：{SOURCE_LABELS[event.source]}
              </span>
              <p className="mt-2">阶段：{event.stage}</p>
              {rejectedCandidates.length > 0 && (
                <div className="mt-3 border-t border-slate-200 pt-3">
                  <p className="font-bold text-slate-600">
                    被过滤候选（{rejectedCandidates.length}）
                  </p>
                  <ul className="mt-2 space-y-1">
                    {rejectedCandidates.map((candidate, candidateIndex) => (
                      <li key={`${candidate.name ?? 'candidate'}-${candidateIndex}`}>
                        - {candidate.name ?? '未命名候选'}：
                        {candidate.reason ?? '不符合当前任务'}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </details>
        )}
      </div>
    </li>
  );
}
