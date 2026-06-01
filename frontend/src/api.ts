const API_BASE = 'http://localhost:8000';

export interface ProviderStatus {
  llm: string;
  poi: string;
  route: string;
  weather: string;
  booking: string;
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

export interface PlanResponseV2 {
  status: string;
  scene: string | null;
  summary: string;
  user_input: string;
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
  share_message: string;
  plan_score: number;
  total_time_min: number;
}

export interface PlanResponse {
  status: string;
  scene: string;
  summary: string;
  constraints: Record<string, any>;
  planning_trace: Array<{ phase: string; message: string }>;
  tool_calls: Array<{
    tool: string;
    input: any;
    output: any;
    success: boolean;
    message: string;
  }>;
  itinerary: Array<{
    time_start: string;
    time_end: string;
    type: string;
    title: string;
    description: string;
    location_id: string | null;
  }>;
  completed_actions: Array<{ type: string; result: any }>;
  fallback_actions: Array<{ type: string; reason: string; suggestion: string }>;
  share_message: string;
  plan_score?: number;
  total_time_min?: number;
}

export async function planQuery(userId: string, query: string): Promise<PlanResponse> {
  const res = await fetch(`${API_BASE}/api/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, query }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function planQueryV2(userId: string, query: string): Promise<PlanResponseV2> {
  const res = await fetch(`${API_BASE}/api/plan/v2`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, query }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getProviderStatus(): Promise<{ app_mode: string; provider_status: ProviderStatus }> {
  const res = await fetch(`${API_BASE}/api/provider-status`);
  return res.json();
}
