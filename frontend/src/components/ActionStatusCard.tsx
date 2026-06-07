import type { ActionResult } from '../api';


type ActionStatusCardProps = {
  action: ActionResult;
};

const STATUS_STYLE = {
  mock_success: {
    label: '模拟成功',
    card: 'bg-emerald-50',
    title: 'text-emerald-800',
    detail: 'text-emerald-700',
  },
  success: {
    label: '成功',
    card: 'bg-emerald-50',
    title: 'text-emerald-800',
    detail: 'text-emerald-700',
  },
  mock_failed: {
    label: '模拟失败',
    card: 'bg-rose-50',
    title: 'text-rose-800',
    detail: 'text-rose-700',
  },
  failed: {
    label: '失败',
    card: 'bg-rose-50',
    title: 'text-rose-800',
    detail: 'text-rose-700',
  },
  pending: {
    label: '待确认',
    card: 'bg-amber-50',
    title: 'text-amber-900',
    detail: 'text-amber-800',
  },
} satisfies Record<
  ActionResult['status'],
  { label: string; card: string; title: string; detail: string }
>;


function actionTitle(action: ActionResult): string {
  if (action.type === 'reservation') return '餐厅预约';
  if (action.type === 'food_order') return '外卖点餐';
  return '计划消息';
}


function detailText(action: ActionResult): string[] {
  const isFailed = action.status === 'mock_failed' || action.status === 'failed';
  const primary = action.type === 'send_message' && !isFailed
    ? action.target === '自己'
      ? '已生成个人计划备忘'
      : `发送给 ${action.target}`
    : action.message;
  const extra = isFailed
    ? [action.details.reason, action.details.suggestion]
    : [];
  return [primary, ...extra]
    .filter((value): value is string => (
      typeof value === 'string' && value.trim().length > 0
    ))
    .filter((value, index, values) => values.indexOf(value) === index);
}


export default function ActionStatusCard({
  action,
}: ActionStatusCardProps) {
  const style = STATUS_STYLE[action.status];
  const details = detailText(action);

  return (
    <div className={`rounded-xl p-3 ${style.card}`}>
      <p className={`text-sm font-semibold ${style.title}`}>
        {actionTitle(action)} · {style.label}
      </p>
      {details.map(detail => (
        <p key={detail} className={`mt-1 text-xs ${style.detail}`}>
          {detail}
        </p>
      ))}
    </div>
  );
}
