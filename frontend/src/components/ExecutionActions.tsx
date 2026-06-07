import type { ActionResult } from '../api';
import ActionStatusCard from './ActionStatusCard';


interface ExecutionActionsProps {
  actions: ActionResult[];
  confirmed: boolean;
  onConfirm: () => void;
}


export default function ExecutionActions({
  actions,
  confirmed,
  onConfirm,
}: ExecutionActionsProps) {
  if (!confirmed) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-600">
          Next step
        </p>
        <div className="mt-2 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="font-bold text-slate-950">计划确认</h3>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              确认后查看点餐、预约和消息生成的模拟结果。
            </p>
          </div>
          <button
            type="button"
            onClick={onConfirm}
            className="min-h-11 shrink-0 rounded-xl bg-blue-600 px-5 text-sm font-bold text-white transition hover:bg-blue-700"
          >
            确认这个计划并查看模拟动作
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-600">
            Mock execution
          </p>
          <h3 className="mt-1 font-bold text-slate-950">模拟执行</h3>
        </div>
        <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-bold text-amber-700">
          不会产生真实交易
        </span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {actions.map(action => (
          <ActionStatusCard
            key={`${action.type}-${action.target}`}
            action={action}
          />
        ))}
      </div>
    </section>
  );
}
