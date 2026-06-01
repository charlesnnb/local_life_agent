import React from 'react';

interface Action {
  type: string;
  result: any;
}

interface FallbackAction {
  type: string;
  reason: string;
  suggestion: string;
}

interface Props {
  completedActions: Action[];
  fallbackActions: FallbackAction[];
}

const TYPE_LABELS: Record<string, string> = {
  ticket_order: '门票订单',
  restaurant_reservation: '餐厅预约',
  extra_service_order: '额外服务',
  ride_order: '打车订单',
  send_message: '消息发送',
};

const OrderResultCard: React.FC<Props> = ({ completedActions, fallbackActions }) => {
  if ((!completedActions || completedActions.length === 0) && (!fallbackActions || fallbackActions.length === 0)) return null;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <span>📋</span> 订单结果
      </h3>

      {/* Completed */}
      {completedActions && completedActions.length > 0 && (
        <div className="space-y-2 mb-3">
          {completedActions.map((action, i) => (
            <div key={i} className="flex items-center gap-3 p-3 bg-green-50 border border-green-100 rounded-lg">
              <span className="text-green-500 text-lg flex-shrink-0">✅</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-800">
                    {TYPE_LABELS[action.type] || action.type}
                  </span>
                  <span className="badge badge-green">已完成</span>
                </div>
                {action.result && (
                  <p className="text-xs text-gray-500 mt-0.5 truncate">
                    {action.result.order_id || action.result.reservation_id || action.result.ride_id || action.result.message_id || action.result.message || 'ok'}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Fallbacks */}
      {fallbackActions && fallbackActions.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-yellow-700">Fallback 记录</p>
          {fallbackActions.map((fb, i) => (
            <div key={i} className="flex items-start gap-3 p-3 bg-yellow-50 border border-yellow-100 rounded-lg">
              <span className="text-yellow-500 text-lg flex-shrink-0">⚠️</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800">{TYPE_LABELS[fb.type] || fb.type}</p>
                <p className="text-xs text-gray-500">{fb.reason}</p>
                <p className="text-xs text-gray-400 mt-0.5">{fb.suggestion}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default OrderResultCard;
