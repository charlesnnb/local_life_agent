import { useEffect, useMemo, useState } from 'react';

import type { ReplanOption, ReplanProposal } from '../api';


interface Props {
  proposal: ReplanProposal;
  onConfirm: (optionId: string) => void | Promise<void>;
  busy: boolean;
}


function ExceptionConfirmationCard({ proposal, onConfirm, busy }: Props) {
  const alternatives = useMemo(
    () => proposal.options.filter(option => option.operation !== 'keep_original'),
    [proposal.options],
  );
  const keepOption = proposal.options.find(
    option => option.operation === 'keep_original',
  );
  const [selectedId, setSelectedId] = useState(
    proposal.selected_option_id ?? alternatives[0]?.option_id ?? '',
  );

  useEffect(() => {
    setSelectedId(
      proposal.selected_option_id ?? alternatives[0]?.option_id ?? '',
    );
  }, [alternatives, proposal.selected_option_id]);

  const selected = proposal.options.find(
    option => option.option_id === selectedId,
  ) ?? alternatives[0];
  const isPending = proposal.status === 'pending';

  return (
    <section
      aria-label="异常确认"
      className="overflow-hidden rounded-2xl border border-blue-200 bg-white shadow-sm"
    >
      <div className="flex flex-col justify-between gap-4 border-b border-blue-100 bg-blue-50 px-5 py-5 sm:flex-row sm:px-6">
        <div>
          <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.12em] text-blue-700">
            <span className="h-2 w-2 rounded-full bg-amber-500 ring-4 ring-amber-100" />
            {isPending ? '需要你确认' : '处理结果'}
          </p>
          <h3 className="mt-2 text-lg font-bold text-slate-950">
            {proposal.exception.title}
          </h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {proposal.exception.message}
          </p>
        </div>
        {Boolean(proposal.exception.impact.mock) && (
          <span className="h-fit w-fit rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-bold text-violet-700">
            Mock 异常
          </span>
        )}
      </div>

      <div className="mx-5 mt-5 rounded-r-lg border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900 sm:mx-6">
        <strong>对计划的影响：</strong>
        {' '}
        {String(
          proposal.exception.impact.summary
          ?? proposal.exception.message,
        )}
      </div>

      {alternatives.length > 1 && isPending && (
        <div className="mx-5 mt-5 flex flex-wrap gap-2 sm:mx-6">
          {alternatives.map(option => (
            <button
              key={option.option_id}
              type="button"
              aria-pressed={option.option_id === selected?.option_id}
              onClick={() => setSelectedId(option.option_id)}
              className={
                option.option_id === selected?.option_id
                  ? 'rounded-full border border-blue-600 bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-700'
                  : 'rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600'
              }
            >
              {option.title}
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="grid gap-3 px-5 py-5 sm:grid-cols-[1fr_auto_1fr] sm:items-stretch sm:px-6">
          <PlanComparison
            label="原计划"
            plan={selected.original_plan}
            muted
          />
          <div className="grid min-h-6 place-items-center font-bold text-blue-600 sm:px-1">
            <span className="rotate-90 text-xl sm:rotate-0">→</span>
          </div>
          <PlanComparison
            label="推荐替代方案"
            plan={selected.proposed_plan}
            option={selected}
          />
        </div>
      )}

      {!selected && keepOption && (
        <p className="mx-5 my-5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600 sm:mx-6">
          {keepOption.description}
        </p>
      )}

      <div className="grid gap-2 px-5 pb-5 sm:flex sm:justify-end sm:px-6 sm:pb-6">
        {isPending ? (
          <>
            <button
              type="button"
              disabled={busy || !keepOption}
              onClick={() => keepOption && onConfirm(keepOption.option_id)}
              className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
            >
              保持原计划
            </button>
            <button
              type="button"
              disabled={busy || !selected}
              onClick={() => selected && onConfirm(selected.option_id)}
              className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700 disabled:opacity-50"
            >
              {busy ? '正在更新计划...' : '接受方案'}
            </button>
          </>
        ) : (
          <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-bold text-emerald-700">
            {proposal.status === 'accepted'
              ? '已接受并更新计划'
              : '已保留原计划'}
          </p>
        )}
      </div>
    </section>
  );
}


function PlanComparison({
  label,
  plan,
  option,
  muted = false,
}: {
  label: string;
  plan: Record<string, unknown>;
  option?: ReplanOption;
  muted?: boolean;
}) {
  const details = Object.entries(plan).filter(
    ([key, value]) => key !== 'name' && value !== null && value !== undefined,
  );

  return (
    <div
      className={
        muted
          ? 'rounded-xl border border-slate-200 bg-slate-50 p-4'
          : 'rounded-xl border border-blue-200 bg-blue-50/40 p-4'
      }
    >
      <p className="text-xs font-bold uppercase tracking-[0.1em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 font-bold text-slate-950">
        {String(plan.name ?? '当前安排')}
      </p>
      {details.map(([key, value]) => (
        <p key={key} className="mt-1 text-xs leading-5 text-slate-600">
          {detailLabel(key)}：{formatValue(key, value)}
        </p>
      ))}
      {option && option.estimated_saved_minutes > 0 && (
        <span className="mt-3 inline-flex rounded-lg bg-emerald-100 px-2.5 py-1.5 text-xs font-bold text-emerald-700">
          预计节省 {option.estimated_saved_minutes} 分钟
        </span>
      )}
      {option
        && option.estimated_saved_minutes === 0
        && option.estimated_delay_minutes > 0 && (
          <span className="mt-3 inline-flex rounded-lg bg-amber-100 px-2.5 py-1.5 text-xs font-bold text-amber-800">
            预计增加 {option.estimated_delay_minutes} 分钟
          </span>
        )}
    </div>
  );
}


function detailLabel(key: string): string {
  return {
    type: '类型',
    distance_km: '距离',
    wait_time_min: '预计等待',
    arrival: '预计到达',
    reservation_time: '预约时间',
    summary: '说明',
  }[key] ?? key;
}


function formatValue(key: string, value: unknown): string {
  if (key === 'distance_km') return `${value} 公里`;
  if (key === 'wait_time_min') return `${value} 分钟`;
  return String(value);
}


export default ExceptionConfirmationCard;
