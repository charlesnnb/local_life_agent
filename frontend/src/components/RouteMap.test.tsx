// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { RoutePlan } from '../api';
import RouteMap from './RouteMap';


const amapMocks = vi.hoisted(() => {
  const mapHandlers = new globalThis.Map<string, () => void>();
  const markerInstances: Array<{
    handlers: globalThis.Map<string, (event?: {
      originalEvent?: { stopPropagation?: () => void };
    }) => void>;
    getPosition: () => unknown;
  }> = [];
  const infoWindowInstances: Array<{
    open: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
  }> = [];
  const mapInstance = {
    add: vi.fn(),
    addControl: vi.fn(),
    remove: vi.fn(),
    setFitView: vi.fn(),
    getZoom: vi.fn(),
    setZoom: vi.fn(),
    on: vi.fn((event: string, handler: () => void) => {
      mapHandlers.set(event, handler);
    }),
    destroy: vi.fn(),
  };
  const Map = vi.fn(function MapConstructor() {
    return mapInstance;
  });
  const Marker = vi.fn(function MarkerConstructor(
    options: Record<string, unknown>,
  ) {
    const handlers = new globalThis.Map();
    const instance = {
      handlers,
      on: vi.fn((
        event: string,
        handler: (event?: {
          originalEvent?: { stopPropagation?: () => void };
        }) => void,
      ) => {
        handlers.set(event, handler);
      }),
      getPosition: vi.fn(() => options.position),
    };
    markerInstances.push(instance);
    return instance;
  });
  const Polyline = vi.fn(function PolylineConstructor() {
    return { on: vi.fn() };
  });
  const InfoWindow = vi.fn(function InfoWindowConstructor() {
    const instance = { open: vi.fn(), close: vi.fn() };
    infoWindowInstances.push(instance);
    return instance;
  });
  const Scale = vi.fn(function ScaleConstructor() {
    return {};
  });
  const ToolBar = vi.fn(function ToolBarConstructor() {
    return {};
  });
  const loadAMap = vi.fn();
  return {
    loadAMap,
    Map,
    Marker,
    Polyline,
    InfoWindow,
    Scale,
    ToolBar,
    mapInstance,
    mapHandlers,
    markerInstances,
    infoWindowInstances,
  };
});

vi.mock('./amapLoader', () => ({
  loadAMap: amapMocks.loadAMap,
}));


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
  ],
  return_to_origin_minutes: 12,
  total_travel_minutes: 24,
  transport: 'taxi',
  source: 'mock',
  polyline: [],
};


describe('RouteMap', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    amapMocks.mapHandlers.clear();
    amapMocks.markerInstances.length = 0;
    amapMocks.infoWindowInstances.length = 0;
    amapMocks.mapInstance.getZoom.mockReturnValue(16);
    amapMocks.loadAMap.mockResolvedValue({
      Map: amapMocks.Map,
      Marker: amapMocks.Marker,
      Polyline: amapMocks.Polyline,
      InfoWindow: amapMocks.InfoWindow,
      Scale: amapMocks.Scale,
      ToolBar: amapMocks.ToolBar,
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it('renders an offline route diagram without a JS key', () => {
    vi.stubEnv('VITE_AMAP_JS_KEY', '');

    render(
      <RouteMap
        route={{
          ...route,
          stops: [
            route.stops[0],
            {
              ...route.stops[0],
              name: '肯德基外卖',
              type: 'food_delivery',
              category: 'food_order',
              label: '外卖',
              estimated_travel_minutes: 0,
            },
            {
              ...route.stops[0],
              name: 'V8台球俱乐部',
              category: 'billiards',
              label: '台球',
              estimated_travel_minutes: 15,
            },
            {
              ...route.stops[0],
              name: '湖心茶馆',
              category: 'tea_house',
              label: '茶馆',
              estimated_travel_minutes: 18,
            },
          ],
        }}
      />,
    );

    expect(screen.getByText('离线路线示意图')).toBeTruthy();
    expect(screen.getByText('起点 → 公园 → 台球 → 茶馆')).toBeTruthy();
    expect(screen.getByText('默认位置：上海徐汇')).toBeTruthy();
    expect(screen.getByText('徐家汇体育公园')).toBeTruthy();
    expect(screen.getByText('V8台球俱乐部')).toBeTruthy();
    expect(screen.getByText('湖心茶馆')).toBeTruthy();
    expect(screen.getByText('预计通勤 12 分钟')).toBeTruthy();
    expect(screen.getByText('预计通勤 15 分钟')).toBeTruthy();
    expect(screen.queryByText('肯德基外卖')).toBeNull();
    expect(amapMocks.loadAMap).not.toHaveBeenCalled();
    expect(amapMocks.Map).not.toHaveBeenCalled();
  });

  it('creates one map instance in React StrictMode', async () => {
    vi.stubEnv('VITE_AMAP_JS_KEY', 'test-js-key');

    render(
      <StrictMode>
        <RouteMap route={route} />
      </StrictMode>,
    );

    await waitFor(() => expect(amapMocks.loadAMap).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(amapMocks.Map).toHaveBeenCalledTimes(1));
  });

  it('redraws overlays without creating another map instance', async () => {
    vi.stubEnv('VITE_AMAP_JS_KEY', 'test-js-key');
    const view = render(<RouteMap route={route} />);
    await waitFor(() => expect(amapMocks.Map).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(amapMocks.mapInstance.add).toHaveBeenCalled());

    view.rerender(
      <RouteMap
        route={{
          ...route,
          stops: [
            ...route.stops,
            {
              ...route.stops[0],
              name: 'V8台球俱乐部',
              category: 'billiards',
              label: '台球',
              lng: 121.442,
              lat: 31.196,
            },
          ],
        }}
      />,
    );

    await waitFor(() => expect(amapMocks.mapInstance.remove).toHaveBeenCalled());
    expect(amapMocks.Map).toHaveBeenCalledTimes(1);
    expect(amapMocks.mapInstance.add.mock.calls.length).toBeGreaterThan(1);
  });

  it('opens marker details only on click and closes them on map click', async () => {
    vi.stubEnv('VITE_AMAP_JS_KEY', 'test-js-key');
    render(<RouteMap route={route} />);
    await waitFor(() => expect(amapMocks.markerInstances.length).toBe(2));

    const originMarker = amapMocks.markerInstances[0];
    expect([...originMarker.handlers.keys()]).toEqual(['click']);
    expect(amapMocks.InfoWindow).not.toHaveBeenCalled();

    const stopPropagation = vi.fn();
    originMarker.handlers.get('click')?.({
      originalEvent: { stopPropagation },
    });

    expect(stopPropagation).toHaveBeenCalledTimes(1);
    expect(amapMocks.InfoWindow).toHaveBeenCalledTimes(1);
    expect(amapMocks.infoWindowInstances[0].open).toHaveBeenCalledWith(
      amapMocks.mapInstance,
      originMarker.getPosition(),
    );

    amapMocks.mapHandlers.get('click')?.();
    expect(amapMocks.infoWindowInstances[0].close).toHaveBeenCalled();
  });

  it('draws the clean route with compact numbered markers', async () => {
    vi.stubEnv('VITE_AMAP_JS_KEY', 'test-js-key');
    render(
      <RouteMap
        route={{
          ...route,
          polyline: [
            [31.1886, 121.4365],
            [31.2, 121.5],
            [31.1837, 121.4375],
          ],
        }}
      />,
    );
    await waitFor(() => expect(amapMocks.Polyline).toHaveBeenCalled());

    expect(amapMocks.Polyline).toHaveBeenCalledWith(
      expect.objectContaining({
        path: [
          [121.4365, 31.1886],
          [121.4375, 31.1837],
        ],
        strokeColor: '#2563eb',
        strokeWeight: 7,
        strokeStyle: 'solid',
        lineJoin: 'round',
        lineCap: 'round',
        showDir: true,
        zIndex: 50,
      }),
    );

    const originContent = (
      amapMocks.Marker.mock.calls[0][0].content as HTMLDivElement
    );
    const stopContent = (
      amapMocks.Marker.mock.calls[1][0].content as HTMLDivElement
    );
    expect(originContent.textContent).toBe('起');
    expect(stopContent.textContent).toBe('1');
    expect(originContent.textContent).not.toContain(route.origin.name);
    expect(amapMocks.Marker.mock.calls[0][0].zIndex).toBe(100);
  });

  it('fits the route with padding and caps an overly close zoom', async () => {
    vi.stubEnv('VITE_AMAP_JS_KEY', 'test-js-key');
    render(<RouteMap route={route} />);
    await waitFor(() => expect(amapMocks.mapInstance.setFitView).toHaveBeenCalled());

    const overlays = amapMocks.mapInstance.setFitView.mock.calls[0][0];
    expect(amapMocks.mapInstance.setFitView).toHaveBeenCalledWith(
      overlays,
      false,
      [60, 60, 60, 60],
    );
    expect(amapMocks.mapInstance.setZoom).toHaveBeenCalledWith(15);
  });
});
