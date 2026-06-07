// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { RoutePlan, TimelineData } from '../api';
import Timeline from './Timeline';


vi.mock('./RouteMap', () => ({
  default: () => <div>地图路线预览</div>,
}));

const route: RoutePlan = {
  origin: { name: '上海徐汇', lat: 31.1886, lng: 121.4365 },
  stops: [
    {
      type: 'activity',
      category: 'park',
      label: '公园',
      name: '徐家汇体育公园',
      lat: 31.1837,
      lng: 121.4375,
      estimated_travel_minutes: 12,
      distance_km: 1.5,
      source: 'amap',
    },
  ],
  return_to_origin_minutes: 10,
  total_travel_minutes: 22,
  transport: 'taxi',
  source: 'amap',
  polyline: [[31.18, 121.43], [31.19, 121.44]],
};

const timeline: TimelineData = {
  total_duration_minutes: 180,
  items: [
    {
      time: '14:00',
      type: 'departure',
      title: '从上海徐汇出发',
      description: '准备出发',
    },
    {
      time: '14:12',
      type: 'activity',
      title: '到达徐家汇体育公园',
      description: '轻松活动',
    },
  ],
};


afterEach(cleanup);


describe('Timeline', () => {
  it('keeps route development metadata hidden from the default view', () => {
    render(<Timeline route={route} timeline={timeline} />);

    expect(screen.getByText('可执行时间线')).toBeTruthy();
    expect(screen.getByText('地图路线预览')).toBeTruthy();
    expect(screen.getByText('总通勤 22 分钟')).toBeTruthy();
    expect(screen.getByText('徐家汇体育公园')).toBeTruthy();
    expect(screen.queryByText(/31\.1886/)).toBeNull();
    expect(screen.queryByText(/polyline/)).toBeNull();
    expect(screen.queryByText(/坐标点/)).toBeNull();
  });

  it('allows both desktop columns to shrink without crushing the timeline', () => {
    render(<Timeline route={route} timeline={timeline} />);

    const layout = screen.getByTestId('timeline-map-layout');
    const timelineCard = screen.getByTestId('timeline-card');
    const mapColumn = screen.getByTestId('route-map-column');

    expect(layout.className).toContain('minmax(0,1.05fr)');
    expect(layout.className).toContain('minmax(0,0.95fr)');
    expect(timelineCard.className).toContain('min-w-0');
    expect(mapColumn.className).toContain('lg:sticky');
  });

  it('uses structured route type before stale route labels', () => {
    render(
      <Timeline
        route={{
          ...route,
          stops: [
            {
              type: 'restaurant',
              category: 'unknown',
              label: '活动',
              name: '川菜馆',
              lat: 31.18,
              lng: 121.43,
              estimated_travel_minutes: 16,
              distance_km: 3,
              source: 'amap',
            },
          ],
        }}
        timeline={{
          total_duration_minutes: 120,
          items: [
            {
              time: '14:00',
              type: 'departure',
              title: '从上海徐汇出发',
              description: '准备出发',
            },
          ],
        }}
      />,
    );

    expect(screen.getByText('餐厅')).toBeTruthy();
    expect(screen.queryByText('活动')).toBeNull();
  });
});
