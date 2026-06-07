import { describe, expect, it } from 'vitest';

import type { RoutePlan } from '../api';
import {
  buildRouteMarkers,
  buildRoutePath,
} from './routeMapUtils';


const route: RoutePlan = {
  origin: {
    name: '默认位置：上海徐汇',
    lat: 31.1886,
    lng: 121.4365,
  },
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
      source: 'mock',
    },
    {
      type: 'activity',
      category: 'billiards',
      label: '台球',
      name: 'V8台球俱乐部',
      lat: 31.196,
      lng: 121.442,
      estimated_travel_minutes: 15,
      distance_km: 2.3,
      source: 'mock',
    },
  ],
  return_to_origin_minutes: 12,
  total_travel_minutes: 39,
  transport: 'taxi',
  source: 'mock',
  polyline: [],
};


describe('buildRoutePath', () => {
  it('falls back to origin and ordered stops using lng-lat coordinates', () => {
    expect(buildRoutePath(route)).toEqual([
      [121.4365, 31.1886],
      [121.4375, 31.1837],
      [121.442, 31.196],
    ]);
  });

  it('uses the clean origin-to-stops route by default when polyline exists', () => {
    expect(buildRoutePath({
      ...route,
      polyline: [
        [31.1886, 121.4365],
        [31.19, 121.45],
        [31.1837, 121.4375],
      ],
    })).toEqual([
      [121.4365, 31.1886],
      [121.4375, 31.1837],
      [121.442, 31.196],
    ]);
  });

  it('converts the current backend lat-lng tuple polyline', () => {
    expect(buildRoutePath({
      ...route,
      polyline: [
        [31.1886, 121.4365],
        [31.1837, 121.4375],
      ],
    }, true)).toEqual([
      [121.4365, 31.1886],
      [121.4375, 31.1837],
    ]);
  });

  it('accepts lng-lat tuples and lng-lat objects', () => {
    expect(buildRoutePath({
      ...route,
      polyline: [
        [121.4365, 31.1886],
        { lng: 121.4375, lat: 31.1837 },
      ],
    }, true)).toEqual([
      [121.4365, 31.1886],
      [121.4375, 31.1837],
    ]);
  });

  it('uses the coordinate fallback when fewer than two polyline points are valid', () => {
    expect(buildRoutePath({
      ...route,
      polyline: [{ lng: 121.4365, lat: 31.1886 }],
    }, true)).toEqual([
      [121.4365, 31.1886],
      [121.4375, 31.1837],
      [121.442, 31.196],
    ]);
  });

  it('excludes delivery-like stops from the coordinate fallback', () => {
    expect(buildRoutePath({
      ...route,
      stops: [
        route.stops[0],
        {
          ...route.stops[1],
          type: 'food_delivery',
          category: 'takeout',
          name: '肯德基外卖',
        },
      ],
    })).toEqual([
      [121.4365, 31.1886],
      [121.4375, 31.1837],
    ]);
  });
});


describe('buildRouteMarkers', () => {
  it('keeps origin and offline stops in route order', () => {
    expect(buildRouteMarkers(route)).toEqual([
      {
        id: 'origin',
        badge: '起',
        name: '默认位置：上海徐汇',
        label: '起点',
        position: [121.4365, 31.1886],
      },
      {
        id: 'stop-1',
        badge: '1',
        name: '徐家汇体育公园',
        label: '公园',
        position: [121.4375, 31.1837],
        estimatedTravelMinutes: 12,
        distanceKm: 1.5,
      },
      {
        id: 'stop-2',
        badge: '2',
        name: 'V8台球俱乐部',
        label: '台球',
        position: [121.442, 31.196],
        estimatedTravelMinutes: 15,
        distanceKm: 2.3,
      },
    ]);
  });

  it('does not render delivery-like route stops as markers', () => {
    expect(buildRouteMarkers({
      ...route,
      stops: [
        route.stops[0],
        {
          ...route.stops[1],
          type: 'order',
          category: 'food_delivery',
          name: '刘大妈螺蛳粉外卖',
        },
      ],
    }).map(marker => marker.name)).toEqual([
      '默认位置：上海徐汇',
      '徐家汇体育公园',
    ]);
  });

  it('offsets a marker that is extremely close to an earlier marker', () => {
    const markers = buildRouteMarkers({
      ...route,
      stops: [
        {
          ...route.stops[0],
          lng: 121.43655,
          lat: 31.18865,
        },
      ],
    });

    expect(markers[0].position).toEqual([121.4365, 31.1886]);
    expect(markers[1].position).toEqual([121.43663, 31.18873]);
  });
});
