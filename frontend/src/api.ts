const API_BASE = 'http://localhost:8000';

export interface ProviderStatus {
  llm: string;
  poi: string;
  route: string;
  weather: string;
  booking: string;
  execution?: string;
}

export interface ProviderStatusV2 {
  app_mode: string;
  providers: ProviderStatus;
  safe_for_live_demo: boolean;
  execution_always_mock: boolean;
  modes_available: Record<string, string>;
}

export interface UserLocation {
  lat?: number | null;
  lng?: number | null;
  accuracy?: number | null;
  source?: string;
  address?: string | null;
}

export interface ParsedIntent {
  city: string | null;
  area: string | null;
  date_or_time: string | null;
  party_size: number | null;
  budget_per_person: number | null;
  scene: string | null;
  cuisine_preferences: string[] | null;
  dislikes_or_restrictions: string[] | null;
  activity_after_meal: string | null;
  transport_preference: string | null;
  indoor_preference: boolean | null;
  raw_user_input: string;
  confidence: number;
  missing_fields: string[];
}

export interface ScoreBreakdown {
  candidate_name: string;
  candidate_id: string;
  distance_score: number;
  route_time_score: number;
  budget_score: number;
  scene_score: number;
  weather_score: number;
  preference_score: number;
  unknown_penalty: number;
  unknown_fields: string[];
  weights: Record<string, number>;
  final_score: number;
}

export interface Candidate {
  id: string;
  name: string;
  type: string;
  address: string;
  longitude: number | null;
  latitude: number | null;
  distance_m: number | null;
  tel: string | null;
  rating: string | number;
  avg_price: string | number;
  open_time: string;
  close_time: string;
  indoor: string | boolean;
  suitable_scenes: string | string[];
  tags: string | string[];
  source: string;
}

export interface WeatherData {
  city: string;
  day_weather: string;
  day_temp: string;
  night_temp: string;
  source: string;
}

export interface ToolCall {
  tool_name?: string;
  tool?: string;
  input?: Record<string, any>;
  success: boolean;
  output?: any;
  message: string;
}

export interface CompletedAction {
  type: string;
  status: string;
  title: string;
  detail: string;
  id?: string;
  result?: any;
}

export interface FallbackAction {
  type?: string;
  reason: string;
  action?: string;
  result?: string;
  suggestion?: string;
}

export interface FeasibilityCheck {
  check: string;
  result: string;
  detail: string;
}

export interface FeasibilityResult {
  feasible: boolean;
  reasons: string[];
  warnings: string[];
  fallback_used: string[];
  checks: FeasibilityCheck[];
  suggested_fallback?: { type: string; reason: string } | null;
}

export interface ActionPlanItem {
  type: string;
  tool: string;
  required: boolean;
  params: Record<string, any>;
}

export interface DebugInfo {
  feasibility: FeasibilityResult;
  action_plan: ActionPlanItem[];
  needs_ticket: boolean;
  demo_scenario?: string;
}

export interface OriginLocation {
  lat?: number;
  lng?: number;
  address?: string;
  district?: string;
  source?: string;
  accuracy?: number | null;
  confidence?: number;
}

export interface PlanResponseV2 {
  status: string;
  version: string;
  scene: string | null;
  summary: string;
  user_input: string;
  constraints: Record<string, any>;
  origin_location: OriginLocation;
  parsed_intent: ParsedIntent;
  provider_status: ProviderStatus;
  candidates: {
    pois: Candidate[];
    restaurants: Candidate[];
  };
  rankings: {
    poi_rankings: ScoreBreakdown[];
    restaurant_rankings: ScoreBreakdown[];
  };
  itinerary: Array<{
    time: string;
    type: string;
    title: string;
    description: string;
    location_id: string | null;
  }>;
  top_picks: {
    poi: Candidate | null;
    restaurant: Candidate | null;
    poi_score: ScoreBreakdown | null;
    restaurant_score: ScoreBreakdown | null;
  };
  weather: WeatherData | null;
  planning_trace: Array<{ phase: string; message: string }>;
  tool_calls: ToolCall[];
  completed_actions: CompletedAction[];
  fallback_actions: FallbackAction[];
  share_message: string;
  explanation: string;
  plan_score: number;
  total_time_min: number;
  debug?: DebugInfo;
}

export interface SSEEvent {
  type: 'trace' | 'tool_call' | 'fallback' | 'partial_itinerary' | 'final' | 'error';
  phase?: string;
  status?: string;
  message?: string;
  tool_name?: string;
  input?: any;
  output?: any;
  reason?: string;
  action?: string;
  result?: string;
  data?: PlanResponseV2 | any;
}

// ── Primary API: plan (V2 pipeline, current main flow) ──────────────

export async function planQuery(
  userId: string,
  query: string,
  location?: UserLocation | null,
  demoScenario?: string,
): Promise<PlanResponseV2> {
  const body: any = { user_id: userId, query };
  if (location) body.location = location;
  if (demoScenario && demoScenario !== 'normal') body.demo_scenario = demoScenario;
  const res = await fetch(`${API_BASE}/api/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Primary streaming API ─────────────────────────────────────────

export function planQueryStream(
  userId: string,
  query: string,
  onEvent: (event: SSEEvent) => void,
  onComplete: () => void,
  onError: (error: string) => void,
  location?: UserLocation | null,
  demoScenario?: string,
): AbortController {
  const controller = new AbortController();
  const body: any = { user_id: userId, query };
  if (location) body.location = location;
  if (demoScenario && demoScenario !== 'normal') body.demo_scenario = demoScenario;

  fetch(`${API_BASE}/api/plan/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).then(async (response) => {
    if (!response.ok) {
      onError(`HTTP ${response.status}`);
      return;
    }
    const reader = response.body?.getReader();
    if (!reader) { onError('No response body'); return; }
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      let eventType = '';
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent({ type: eventType as any, ...data });
          } catch {}
          eventType = '';
        }
      }
    }
    onComplete();
  }).catch((err) => {
    if (err.name !== 'AbortError') onError(err.message);
  });

  return controller;
}

// ── Backward-compatible aliases (kept for existing consumers) ──────

export async function planQueryV2(
  userId: string,
  query: string,
  location?: UserLocation | null,
  demoScenario?: string,
): Promise<PlanResponseV2> {
  return planQuery(userId, query, location, demoScenario);
}

export function planQueryV2Stream(
  userId: string,
  query: string,
  onEvent: (event: SSEEvent) => void,
  onComplete: () => void,
  onError: (error: string) => void,
  location?: UserLocation | null,
  demoScenario?: string,
): AbortController {
  return planQueryStream(userId, query, onEvent, onComplete, onError, location, demoScenario);
}

// ── Provider status ─────────────────────────────────────────────────

export async function getProviderStatus(): Promise<{ app_mode: string; provider_status: ProviderStatus }> {
  const res = await fetch(`${API_BASE}/api/provider-status`);
  return res.json();
}

export async function getProviderStatusV2(): Promise<ProviderStatusV2> {
  const res = await fetch(`${API_BASE}/api/provider/status`);
  return res.json();
}

export async function switchAppMode(mode: string): Promise<{
  status: string; app_mode: string; providers: ProviderStatus; safe_for_live_demo: boolean;
}> {
  const res = await fetch(`${API_BASE}/api/mode/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ app_mode: mode }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown' }));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}
