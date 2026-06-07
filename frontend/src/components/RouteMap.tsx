import { useEffect, useRef, useState } from 'react';

import type { RoutePlan } from '../api';
import {
  buildRouteMarkers,
  buildRoutePath,
} from './routeMapUtils';
import type {
  LngLat,
  RouteMarkerData,
} from './routeMapUtils';
import { loadAMap } from './amapLoader';
import OfflineRouteDiagram from './OfflineRouteDiagram';


interface RouteMapProps {
  route: RoutePlan | null;
}

type MapStatus = 'loading' | 'ready' | 'error';

interface AMapOverlay {
  on(event: string, handler: (event?: AMapEvent) => void): void;
}

interface AMapEvent {
  originalEvent?: {
    stopPropagation?: () => void;
  };
}

interface AMapMarker extends AMapOverlay {
  getPosition(): LngLat;
}

interface AMapInfoWindow {
  open(map: AMapMap, position: LngLat): void;
  close(): void;
}

interface AMapMap {
  add(overlays: AMapOverlay | AMapOverlay[]): void;
  addControl(control: unknown): void;
  remove(overlays: AMapOverlay | AMapOverlay[]): void;
  setFitView(
    overlays?: AMapOverlay[],
    immediately?: boolean,
    avoid?: number[],
  ): void;
  getZoom(): number;
  setZoom(zoom: number): void;
  on(event: string, handler: () => void): void;
  destroy(): void;
}

interface AMapNamespace {
  Map: new (
    container: HTMLDivElement,
    options?: Record<string, unknown>,
  ) => AMapMap;
  Marker: new (options: Record<string, unknown>) => AMapMarker;
  Polyline: new (options: Record<string, unknown>) => AMapOverlay;
  InfoWindow: new (options: Record<string, unknown>) => AMapInfoWindow;
  Scale: new () => unknown;
  ToolBar: new () => unknown;
}

const USE_DETAILED_POLYLINE = false;


function RouteMap({ route }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<AMapMap | null>(null);
  const amapRef = useRef<AMapNamespace | null>(null);
  const initGenerationRef = useRef(0);
  const overlaysRef = useRef<AMapOverlay[]>([]);
  const infoWindowRef = useRef<AMapInfoWindow | null>(null);
  const [status, setStatus] = useState<MapStatus>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const apiKey = import.meta.env.VITE_AMAP_JS_KEY?.trim();
  const securityCode =
    import.meta.env.VITE_AMAP_SECURITY_JS_CODE?.trim();
  const hasRoute = route !== null;

  useEffect(() => {
    if (!apiKey || !hasRoute) return;

    const generation = initGenerationRef.current + 1;
    initGenerationRef.current = generation;
    setStatus('loading');
    setErrorMessage('');

    if (securityCode) {
      window._AMapSecurityConfig = {
        securityJsCode: securityCode,
      };
    }

    Promise.resolve()
      .then(() => {
        if (generation !== initGenerationRef.current) return null;
        return loadAMap({
          key: apiKey,
          version: '2.0',
          plugins: ['AMap.Scale', 'AMap.ToolBar'],
        });
      })
      .then(rawAMap => {
        if (
          !rawAMap
          || generation !== initGenerationRef.current
          || !containerRef.current
        ) {
          return;
        }
        if (mapRef.current) return;
        const AMap = rawAMap as AMapNamespace;
        const map = new AMap.Map(containerRef.current, {
          zoom: 12,
          viewMode: '2D',
        });
        map.on('click', () => infoWindowRef.current?.close());
        map.addControl(new AMap.Scale());
        map.addControl(new AMap.ToolBar());
        mapRef.current = map;
        amapRef.current = AMap;
        setStatus('ready');
      })
      .catch(error => {
        if (generation !== initGenerationRef.current) return;
        setStatus('error');
        setErrorMessage(
          error instanceof Error ? error.message : '高德地图加载失败',
        );
      });

    return () => {
      if (generation === initGenerationRef.current) {
        initGenerationRef.current += 1;
      }
      infoWindowRef.current?.close();
      if (mapRef.current && overlaysRef.current.length > 0) {
        mapRef.current.remove(overlaysRef.current);
      }
      mapRef.current?.destroy();
      overlaysRef.current = [];
      infoWindowRef.current = null;
      mapRef.current = null;
      amapRef.current = null;
    };
  }, [apiKey, hasRoute, securityCode]);

  useEffect(() => {
    const map = mapRef.current;
    const AMap = amapRef.current;
    if (status !== 'ready' || !map || !AMap || !route) return;

    if (overlaysRef.current.length > 0) {
      map.remove(overlaysRef.current);
      overlaysRef.current = [];
    }
    infoWindowRef.current?.close();

    const overlays: AMapOverlay[] = [];
    const markers = buildRouteMarkers(route).map(markerData => {
      const marker = new AMap.Marker({
        position: markerData.position,
        anchor: 'bottom-center',
        content: createMarkerContent(markerData),
        zIndex: 100,
      });
      const openInfoWindow = (event?: AMapEvent) => {
        event?.originalEvent?.stopPropagation?.();
        infoWindowRef.current?.close();
        const infoWindow = new AMap.InfoWindow({
          anchor: 'bottom-center',
          content: createInfoWindowContent(markerData),
        });
        infoWindow.open(map, marker.getPosition());
        infoWindowRef.current = infoWindow;
      };
      marker.on('click', openInfoWindow);
      return marker;
    });
    overlays.push(...markers);

    const path = buildRoutePath(route, USE_DETAILED_POLYLINE);
    if (path.length > 1) {
      overlays.push(new AMap.Polyline({
        path,
        strokeColor: '#2563eb',
        strokeWeight: 7,
        strokeOpacity: 0.9,
        strokeStyle: 'solid',
        lineJoin: 'round',
        lineCap: 'round',
        showDir: true,
        zIndex: 50,
      }));
    }

    if (overlays.length > 0) {
      map.add(overlays);
      overlaysRef.current = overlays;
      map.setFitView(overlays, false, [60, 60, 60, 60]);
      if (map.getZoom() > 15) {
        map.setZoom(15);
      }
    }

    return () => {
      if (mapRef.current === map && overlaysRef.current === overlays) {
        map.remove(overlays);
        overlaysRef.current = [];
      }
      infoWindowRef.current?.close();
    };
  }, [route, status]);

  if (!route) {
    return (
      <MapCard>
        <MapMessage
          title="暂无路线可展示"
          description="生成包含线下地点的计划后，地图会显示完整路线。"
        />
      </MapCard>
    );
  }

  if (!apiKey) {
    return (
      <MapCard>
        <OfflineRouteDiagram route={route} />
      </MapCard>
    );
  }

  return (
    <MapCard>
      <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
        <div
          ref={containerRef}
          className="w-full overflow-hidden rounded-xl"
          style={{ width: '100%', height: '380px' }}
        />
        {status === 'loading' && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-50/90 text-sm font-medium text-slate-500">
            正在加载地图路线...
          </div>
        )}
        {status === 'error' && (
          <div className="absolute inset-0 flex items-center justify-center bg-amber-50 p-6 text-center">
            <div>
              <p className="font-semibold text-amber-900">地图加载失败</p>
              <p className="mt-2 text-sm text-amber-700">
                {errorMessage || '请检查高德 JS API Key 与安全密钥配置。'}
              </p>
            </div>
          </div>
        )}
      </div>
    </MapCard>
  );
}


function MapCard({ children }: { children: React.ReactNode }) {
  return (
    <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
          Map
        </p>
        <h3 className="mt-1 text-lg font-bold">地图路线</h3>
        <p className="mt-1 text-sm text-slate-500">
          按计划顺序展示地点与路线
        </p>
      </div>
      {children}
    </section>
  );
}


function MapMessage({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-56 items-center justify-center rounded-xl border border-dashed border-blue-200 bg-blue-50 px-6 text-center">
      <div>
        <p className="font-semibold text-blue-950">{title}</p>
        <p className="mt-2 text-sm leading-6 text-blue-700">{description}</p>
      </div>
    </div>
  );
}


function createMarkerContent(marker: RouteMarkerData): HTMLDivElement {
  const root = document.createElement('div');
  root.textContent = marker.badge;
  root.style.display = 'inline-flex';
  root.style.alignItems = 'center';
  root.style.justifyContent = 'center';
  root.style.width = '34px';
  root.style.height = '34px';
  root.style.borderRadius = '9999px';
  root.style.border = '3px solid white';
  root.style.background = marker.id === 'origin' ? '#16a34a' : '#2563eb';
  root.style.color = 'white';
  root.style.fontSize = '15px';
  root.style.fontWeight = '800';
  root.style.boxShadow = (
    marker.id === 'origin'
      ? '0 8px 18px rgba(22, 163, 74, 0.32)'
      : '0 8px 18px rgba(37, 99, 235, 0.35)'
  );
  return root;
}


function createInfoWindowContent(marker: RouteMarkerData): HTMLDivElement {
  const root = document.createElement('div');
  root.style.width = '220px';
  root.style.maxWidth = '240px';
  root.style.padding = '4px';
  root.style.color = '#0f172a';

  const title = document.createElement('p');
  title.textContent = marker.name;
  title.style.margin = '0';
  title.style.fontSize = '14px';
  title.style.fontWeight = '700';
  root.append(title);

  const type = document.createElement('p');
  type.textContent = `类型：${marker.label}`;
  type.style.margin = '6px 0 0';
  type.style.color = '#475569';
  type.style.fontSize = '12px';
  root.append(type);

  if (marker.estimatedTravelMinutes !== undefined) {
    const travel = document.createElement('p');
    travel.textContent = (
      `预计通勤：${marker.estimatedTravelMinutes} 分钟`
      + (
        marker.distanceKm !== undefined
          ? ` · ${marker.distanceKm} 公里`
          : ''
      )
    );
    travel.style.margin = '4px 0 0';
    travel.style.color = '#475569';
    travel.style.fontSize = '12px';
    root.append(travel);
  }

  return root;
}


export default RouteMap;
