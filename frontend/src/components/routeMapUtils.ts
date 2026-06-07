import type { RoutePlan } from '../api.ts';


export type LngLat = [number, number];

export interface RouteMarkerData {
  id: string;
  badge: string;
  name: string;
  label: string;
  position: LngLat;
  estimatedTravelMinutes?: number;
  distanceKm?: number;
}


export function buildRoutePath(
  route: RoutePlan,
  useDetailedPolyline = false,
): LngLat[] {
  const references = routeReferencePoints(route);
  if (!useDetailedPolyline) return references;

  const polyline = route.polyline
    .map(point => normalizePolylinePoint(point, references))
    .filter((point): point is LngLat => point !== null);

  return polyline.length > 1 ? polyline : references;
}


export function buildRouteMarkers(route: RoutePlan): RouteMarkerData[] {
  const origin = toLngLat(route.origin.lng, route.origin.lat);
  const markers: RouteMarkerData[] = [];
  const markerPositions: LngLat[] = [];

  if (origin) {
    markerPositions.push(origin);
    markers.push({
      id: 'origin',
      badge: '起',
      name: route.origin.name,
      label: '起点',
      position: origin,
    });
  }

  getRouteStops(route).forEach((stop, index) => {
    const routePosition = toLngLat(stop.lng, stop.lat);
    if (!routePosition) return;
    const position = offsetOverlappingMarker(
      routePosition,
      markerPositions,
    );
    markerPositions.push(routePosition);
    markers.push({
      id: `stop-${index + 1}`,
      badge: String(index + 1),
      name: stop.name,
      label: stop.label || stop.category || '活动',
      position,
      estimatedTravelMinutes: stop.estimated_travel_minutes,
      distanceKm: stop.distance_km,
    });
  });

  return markers;
}


function offsetOverlappingMarker(
  position: LngLat,
  previousPositions: LngLat[],
): LngLat {
  const overlapCount = previousPositions.filter(previous => (
    Math.abs(previous[0] - position[0]) < 0.0001
    && Math.abs(previous[1] - position[1]) < 0.0001
  )).length;
  if (overlapCount === 0) return position;

  const offset = overlapCount * 0.00008;
  return [position[0] + offset, position[1] + offset];
}


function routeReferencePoints(route: RoutePlan): LngLat[] {
  return [
    toLngLat(route.origin.lng, route.origin.lat),
    ...getRouteStops(route).map(stop => toLngLat(stop.lng, stop.lat)),
  ].filter((point): point is LngLat => point !== null);
}


export function getRouteStops(route: RoutePlan): RoutePlan['stops'] {
  const deliveryTerms = new Set([
    'food_delivery',
    'food_order',
    'order',
    'takeout',
    'delivery',
    '外卖',
    '点餐',
  ]);
  return route.stops.filter(stop => (
    !deliveryTerms.has(String(stop.type).toLowerCase())
    && !deliveryTerms.has(String(stop.category).toLowerCase())
  ));
}


function normalizePolylinePoint(
  point: RoutePlan['polyline'][number],
  references: LngLat[],
): LngLat | null {
  if (!Array.isArray(point)) {
    return toLngLat(point.lng, point.lat);
  }
  if (point.length < 2) return null;

  const first = Number(point[0]);
  const second = Number(point[1]);
  const direct = toLngLat(first, second);
  const swapped = toLngLat(second, first);
  if (direct && !swapped) return direct;
  if (swapped && !direct) return swapped;
  if (!direct || !swapped) return null;

  return nearestReferenceDistance(direct, references)
    <= nearestReferenceDistance(swapped, references)
    ? direct
    : swapped;
}


function toLngLat(lng: number, lat: number): LngLat | null {
  if (
    !Number.isFinite(lng)
    || !Number.isFinite(lat)
    || Math.abs(lng) > 180
    || Math.abs(lat) > 90
  ) {
    return null;
  }
  return [lng, lat];
}


function nearestReferenceDistance(
  point: LngLat,
  references: LngLat[],
): number {
  if (references.length === 0) return 0;
  return Math.min(
    ...references.map(reference => (
      (point[0] - reference[0]) ** 2
      + (point[1] - reference[1]) ** 2
    )),
  );
}
