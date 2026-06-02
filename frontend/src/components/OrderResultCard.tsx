import React from 'react';

interface CompletedAction {
  type: string;
  status?: string;
  title?: string;
  detail?: string;
  id?: string;
  result?: any;
}

interface FallbackAction {
  type?: string;
  reason: string;
  action?: string;
  result?: string;
  suggestion?: string;
}

interface Props {
  completedActions: CompletedAction[];
  fallbackActions: FallbackAction[];
}

const TYPE_LABELS: Record<string, string> = {
  ticket_order: '门票订单',
  restaurant_reservation: '餐厅预约',
  extra_service_order: '额外服务',
  ride_order: '打车订单',
  send_message: '消息发送',
  ticket_order_fallback: '门票Fallback',
  reservation_fallback: '预约Fallback',
  extra_service_skipped: '额外服务跳过',
  ride_fallback: '打车Fallback',
  message_fallback: '消息Fallback',
  execution_error: '执行错误',
};

const OrderResultCard: React.FC<Props> = ({ completedActions, fallbackActions }) => {
  const hasCompleted = completedActions && completedActions.length > 0;
  const hasFallbacks = fallbackActions && fallbackActions.length > 0;

  if (!hasCompleted && !hasFallbacks) return null;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <span>📋</span> 订单结果
      </h3>

      {/* Completed */}
      {hasCompleted && (
        <div className="space-y-2 mb-3">
          {completedActions.map((action, i) => {
            const label = action.title || TYPE_LABELS[action.type] || action.type;
            const detail = action.detail || (action.result
              ? (action.result.order_id || action.result.reservation_id || action.result.ride_id || action.result.message_id || action.result.message || 'ok')
              : '');
            return (
              <div key={i} className="flex items-center gap-3 p-3 bg-green-50 border border-green-100 rounded-lg">
                <span className="text-green-500 text-lg flex-shrink-0">✅</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-800">{label}</span>
                    <span className="badge badge-green">{action.status || '已完成'}</span>
                  </div>
                  {detail && (
                    <p className="text-xs text-gray-500 mt-0.5 truncate">{detail}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Fallbacks */}
      {hasFallbacks && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-yellow-700">Fallback 记录</p>
          {fallbackActions.map((fb, i) => {
            const fbType = fb.type || '';
            const label = TYPE_LABELS[fbType] || fbType || 'Fallback';
            const reason = fb.reason || '';
            const detail = fb.action || fb.result || fb.suggestion || '';
            return (
              <div key={i} className="flex items-start gap-3 p-3 bg-yellow-50 border border-yellow-100 rounded-lg">
                <span className="text-yellow-500 text-lg flex-shrink-0">⚠️</span>
                <div className="flex-1 min-w-0">
                  {label && <p className="text-sm font-medium text-gray-800">{label}</p>}
                  {reason && <p className="text-xs text-gray-500">{reason}</p>}
                  {detail && <p className="text-xs text-gray-400 mt-0.5">{detail}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default OrderResultCard;
