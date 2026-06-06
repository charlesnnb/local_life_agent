import { RoutePlan, TimelineData } from '../api';


interface Props {
  route: RoutePlan;
  timeline: TimelineData;
}


const TYPE_LABELS: Record<string, string> = {
  departure: '出发',
  activity: '活动',
  transfer: '转场',
  restaurant: '用餐',
  bar: '酒吧',
  hotel: '酒店',
  food_order: '点餐',
  delivery: '送达',
  break: '休息',
  return: '返程',
  arrival: '完成',
};

const sourceLabel = (source: string) => {
  if (source === 'amap') return 'AMap';
  if (source === 'mixed') return 'AMap + Mock';
  return 'Mock';
};

const stopLabel = (type: RoutePlan['stops'][number]['type']) => {
  if (type === 'activity') return '活动';
  if (type === 'bar') return '酒吧';
  if (type === 'hotel') return '酒店';
  return '餐厅';
};


function Timeline({ route, timeline }: Props) {
  const routePoints = [
    {
      label: '起点',
      name: route.origin.name,
      detail: `${route.origin.lat.toFixed(4)}, ${route.origin.lng.toFixed(4)}`,
      source: route.source === 'amap' ? 'amap' : 'mock',
    },
    ...route.stops.map(stop => ({
      label: stopLabel(stop.type),
      name: stop.name,
      detail: `${stop.estimated_travel_minutes} 分钟 · ${stop.distance_km} 公里`,
      source: stop.source,
    })),
  ];

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
              Route
            </p>
            <h3 className="mt-1 text-lg font-bold">路线概览</h3>
          </div>
          <div className="rounded-xl bg-blue-50 px-4 py-2 text-right">
            <p className="text-xs text-blue-600">总通勤时间</p>
            <p className="text-xl font-bold text-blue-900">
              {route.total_travel_minutes} 分钟
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          {routePoints.map((point, index) => (
            <div
              key={`${point.label}-${point.name}`}
              className="relative rounded-xl border border-slate-200 bg-slate-50 p-4"
            >
              <p className="text-xs font-semibold text-slate-400">
                {index + 1}. {point.label}
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{point.name}</p>
              <p className="mt-1 text-xs text-slate-500">{point.detail}</p>
              <span className="mt-2 inline-flex rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-slate-500">
                地点来源：{sourceLabel(point.source)}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          最终站返程预计 {route.return_to_origin_minutes} 分钟，路线来源：
          {sourceLabel(route.source)}
          {route.polyline.length > 0
            ? `，已保存 ${route.polyline.length} 个 polyline 坐标点`
            : '，当前无 polyline 数据'}
          。
        </p>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
              Timeline
            </p>
            <h3 className="mt-1 text-lg font-bold">可执行时间线</h3>
          </div>
          <p className="text-xs text-slate-500">
            总时长约 {Math.round(timeline.total_duration_minutes / 6) / 10} 小时
          </p>
        </div>

        <div className="mt-6">
          {timeline.items.map((item, index) => (
            <div key={`${item.time}-${item.type}`} className="flex gap-4">
              <div className="flex w-14 flex-col items-center">
                <p className="text-xs font-bold text-blue-700">{item.time}</p>
                <div className="mt-2 h-3 w-3 rounded-full border-2 border-blue-600 bg-white" />
                {index < timeline.items.length - 1 && (
                  <div className="min-h-14 flex-1 w-px bg-slate-200" />
                )}
              </div>
              <div className="pb-6">
                <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-500">
                  {TYPE_LABELS[item.type] || item.type}
                </span>
                <p className="mt-2 font-semibold text-slate-900">{item.title}</p>
                <p className="mt-1 text-sm leading-6 text-slate-500">{item.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}


export default Timeline;
