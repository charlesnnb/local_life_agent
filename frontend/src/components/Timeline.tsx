import type { RoutePlan, TimelineData } from '../api';
import RouteMap from './RouteMap';


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
  free_time: '自由安排',
  return: '返程',
  arrival: '完成',
};


const ROUTE_STOP_TYPE_LABELS: Record<string, string> = {
  activity: '活动',
  restaurant: '餐厅',
  bar: '酒吧',
  hotel: '酒店',
  food_delivery: '外卖',
  food_order: '外卖',
  order: '外卖',
  takeout: '外卖',
};

const ROUTE_STOP_CATEGORY_LABELS: Record<string, string> = {
  restaurant: '餐厅',
  cafe: '饮品',
  tea_drink: '茶饮',
  tea_house: '茶饮',
};


const FREE_TIME_DURATION_PATTERN = /(距离“[^”]+”还有约 )(\d+) 分钟/;


function formatFreeTimeDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} 分钟`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  if (remainingMinutes === 0) {
    return `${hours} 小时`;
  }

  return `${hours} 小时 ${remainingMinutes} 分钟`;
}


function formatFreeTimeDescription(description: string): string {
  return description.replace(
    FREE_TIME_DURATION_PATTERN,
    (_, prefix: string, minutesText: string) => (
      `${prefix}${formatFreeTimeDuration(Number(minutesText))}`
    ),
  );
}


function routeStopLabel(stop: RoutePlan['stops'][number]): string {
  return ROUTE_STOP_CATEGORY_LABELS[stop.category]
    || ROUTE_STOP_TYPE_LABELS[stop.type]
    || stop.label
    || stop.category
    || stop.type;
}


export default function Timeline({ route, timeline }: Props) {
  const routePoints = [
    { label: '起点', name: route.origin.name },
    ...route.stops.map(stop => ({
      label: routeStopLabel(stop),
      name: stop.name,
    })),
  ];
  const sourceLabel = route.source === 'amap'
    ? 'AMap'
    : route.source === 'mixed'
      ? 'AMap + Mock fallback'
      : 'Mock';

  return (
    <section className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm sm:px-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-600">
              Route overview
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              {routePoints.map((point, index) => (
                <span key={`${point.label}-${point.name}`} className="contents">
                  {index > 0 && (
                    <span aria-hidden="true" className="font-bold text-blue-400">
                      →
                    </span>
                  )}
                  <span className="rounded-lg bg-slate-100 px-2.5 py-1.5 font-semibold text-slate-700">
                    <span className="text-xs text-slate-400">{point.label}</span>
                    <span className="ml-1">{point.name}</span>
                  </span>
                </span>
              ))}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2 text-xs">
            <span className="rounded-full bg-blue-50 px-3 py-1.5 font-bold text-blue-700">
              总通勤 {route.total_travel_minutes} 分钟
            </span>
            <span className="rounded-full bg-slate-100 px-3 py-1.5 font-semibold text-slate-500">
              {sourceLabel}
            </span>
          </div>
        </div>
      </div>

      <div
        data-testid="timeline-map-layout"
        className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]"
      >
        <section
          data-testid="timeline-card"
          className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
        >
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-600">
                Timeline
              </p>
              <h3 className="mt-1 text-lg font-bold text-slate-950">
                可执行时间线
              </h3>
            </div>
            <p className="text-xs text-slate-500">
              约 {Math.round(timeline.total_duration_minutes / 6) / 10} 小时
            </p>
          </div>

          <div className="mt-6">
            {timeline.items.map((item, index) => (
              <div key={`${item.time}-${item.type}-${index}`} className="flex gap-3">
                <div className="flex w-12 shrink-0 flex-col items-center">
                  <p className="text-xs font-bold text-blue-700">{item.time}</p>
                  <div className="mt-2 h-3 w-3 rounded-full border-2 border-blue-600 bg-white" />
                  {index < timeline.items.length - 1 && (
                    <div className="min-h-12 w-px flex-1 bg-slate-200" />
                  )}
                </div>
                <div className="min-w-0 pb-6">
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-500">
                    {TYPE_LABELS[item.type] || item.type}
                  </span>
                  <p className="mt-2 font-bold text-slate-900">{item.title}</p>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    {item.type === 'free_time'
                      ? formatFreeTimeDescription(item.description)
                      : item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div
          data-testid="route-map-column"
          className="min-w-0 lg:sticky lg:top-24"
        >
          <RouteMap route={route} />
        </div>
      </div>
    </section>
  );
}
