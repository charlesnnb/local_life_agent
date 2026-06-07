import type { RoutePlan } from '../api';
import { getRouteStops } from './routeMapUtils';


interface OfflineRouteDiagramProps {
  route: RoutePlan;
}


export default function OfflineRouteDiagram({
  route,
}: OfflineRouteDiagramProps) {
  const stops = getRouteStops(route);
  const routeSummary = [
    '起点',
    ...stops.map(stop => stop.label || stop.category || '活动'),
  ].join(' → ');
  const points = [
    {
      id: 'origin',
      badge: '起',
      type: '起点',
      name: route.origin.name,
      travel: null,
    },
    ...stops.map((stop, index) => ({
      id: `stop-${index + 1}`,
      badge: String(index + 1),
      type: stop.label || stop.category || '活动',
      name: stop.name,
      travel: `预计通勤 ${stop.estimated_travel_minutes} 分钟`,
    })),
  ];

  return (
    <div
      aria-label="离线路线示意图"
      className="overflow-hidden rounded-xl border border-blue-100 bg-gradient-to-br from-blue-50 via-white to-slate-50"
    >
      <div className="border-b border-blue-100 px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold text-blue-950">离线路线示意图</p>
            <p className="mt-1 text-sm font-medium text-blue-700">
              {routeSummary}
            </p>
          </div>
          <span className="rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-semibold text-blue-700">
            无地图 Key · 本地展示
          </span>
        </div>
      </div>

      <div className="overflow-x-auto p-5">
        <div className="flex min-w-max items-stretch">
          {points.map((point, index) => (
            <div key={point.id} className="flex items-center">
              <div className="w-44 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-center gap-3">
                  <span
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${
                      point.id === 'origin' ? 'bg-emerald-600' : 'bg-blue-600'
                    }`}
                  >
                    {point.badge}
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-400">
                      {point.type}
                    </p>
                    <p className="mt-1 truncate text-sm font-bold text-slate-900">
                      {point.name}
                    </p>
                  </div>
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  {point.travel || '从这里开始行程'}
                </p>
              </div>

              {index < points.length - 1 && (
                <svg
                  aria-hidden="true"
                  className="mx-2 shrink-0"
                  width="42"
                  height="24"
                  viewBox="0 0 42 24"
                >
                  <path
                    d="M2 12H36"
                    fill="none"
                    stroke="#93c5fd"
                    strokeDasharray="4 4"
                    strokeLinecap="round"
                    strokeWidth="3"
                  />
                  <path
                    d="M30 6L38 12L30 18"
                    fill="none"
                    stroke="#2563eb"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="3"
                  />
                </svg>
              )}
            </div>
          ))}
        </div>
      </div>

      <p className="border-t border-blue-100 px-5 py-3 text-xs text-slate-500">
        当前未配置高德 JS Key，路线顺序与通勤时间仍来自本次计划。
      </p>
    </div>
  );
}
