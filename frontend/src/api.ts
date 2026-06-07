const API_BASE = '';

export interface UserTask {
  task_id: string;
  time_window: string;
  task_type:
    | 'food_delivery'
    | 'poi_search'
    | 'restaurant_search'
    | 'hotel_search'
    | 'food_order'
    | 'activity_search'
    | 'restaurant_visit'
    | 'bar_visit'
    | 'route_stop'
    | 'message'
    | 'unknown';
  target: string | null;
  search_query: string | null;
  tool_name: string;
  route_needed: boolean;
  description: string;
  priority: number;
  companions: string[];
  child_age: number | null;
  constraints: string[];
}

export interface TaskPlan {
  scene: string;
  mood: string | null;
  time_windows: string[];
  tasks: UserTask[];
  constraints: Record<string, unknown>;
}

export interface UserIntent {
  raw_query: string;
  scene: string;
  time_window: string;
  time_windows: string[];
  tasks: UserTask[];
  duration_hours: number[];
  companions: string[];
  party_size: number;
  child_age: number | null;
  gender_mix: { male: number; female: number } | null;
  distance_preference: 'nearby' | 'normal' | 'flexible';
  activity_preferences: string[];
  diet_preferences: string[];
  budget_preference: 'not_expensive' | 'normal' | 'flexible';
  avoid: string[];
  weather_constraint: 'rain' | 'snow' | 'hot' | 'cold' | null;
  city: string | null;
}

export interface UserPreference {
  activity_types: string[];
  max_travel_minutes: 15 | 30 | 45;
  dining_preferences: string[];
  activity_intensity: 'light' | 'medium' | 'high';
  budget_level: 'low' | 'medium' | 'high';
  prefer_indoor: boolean;
  prefer_low_wait: boolean;
}

export interface PreferenceWeights {
  distance_weight: number;
  activity_match_weight: number;
  child_friendly_weight: number;
  diet_match_weight: number;
  popularity_weight: number;
  budget_weight: number;
  indoor_weight: number;
  low_wait_weight: number;
}

export interface PreferenceProfile {
  preference: UserPreference;
  weights: PreferenceWeights;
}

export interface PreferenceSetupData extends PreferenceProfile {
  options: {
    activity_types: string[];
    max_travel_minutes: number[];
    dining_preferences: string[];
    activity_intensity: string[];
    budget_level: string[];
  };
}

export interface PlanStep {
  time: string;
  action: string;
  description: string;
  place: string | null;
  reason: string | null;
  source: string | null;
}

export interface ActionResult {
  type: 'reservation' | 'send_message' | 'food_order';
  target: string;
  status: 'mock_success' | 'mock_failed' | 'success' | 'failed' | 'pending';
  message: string | null;
  details: Record<string, unknown>;
}

export interface RuntimeMode {
  mode: 'demo' | 'hybrid' | 'live';
  llm: 'mock' | 'deepseek';
  amap: 'mock' | 'amap';
  actions: 'mock' | 'mock_fallback' | 'live';
}

export interface PlanException {
  exception_id: string;
  exception_type: string;
  source_task_id: string | null;
  severity: string;
  title: string;
  message: string;
  impact: Record<string, unknown>;
  status: string;
}

export interface ReplanOption {
  option_id: string;
  title: string;
  description: string;
  changes: string[];
  estimated_delay_minutes: number;
  estimated_saved_minutes: number;
  replacement_place: Record<string, unknown> | null;
  operation:
    | 'replace_restaurant'
    | 'replace_activity'
    | 'adjust_reservation'
    | 'keep_original';
  original_plan: Record<string, unknown>;
  proposed_plan: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface ReplanProposal {
  proposal_id: string;
  exception: PlanException;
  options: ReplanOption[];
  requires_consent: boolean;
  status: 'pending' | 'accepted' | 'kept';
  selected_option_id: string | null;
}

export interface RoutePlan {
  origin: {
    name: string;
    lat: number;
    lng: number;
  };
  stops: Array<{
    type:
      | 'activity'
      | 'restaurant'
      | 'bar'
      | 'hotel'
      | 'food_delivery'
      | 'food_order'
      | 'order'
      | 'takeout';
    category: string;
    label: string;
    name: string;
    lat: number;
    lng: number;
    estimated_travel_minutes: number;
    distance_km: number;
    source: string;
  }>;
  return_to_origin_minutes: number;
  total_travel_minutes: number;
  transport: string;
  source: string;
  polyline: Array<[number, number] | { lng: number; lat: number }>;
}

export interface TimelineItem {
  time: string;
  type:
    | 'departure'
    | 'activity'
    | 'transfer'
    | 'restaurant'
    | 'bar'
    | 'hotel'
    | 'food_order'
    | 'delivery'
    | 'break'
    | 'free_time'
    | 'return'
    | 'arrival';
  title: string;
  description: string;
}

export interface TimelineData {
  items: TimelineItem[];
  total_duration_minutes: number;
}

export interface PlanResponse {
  user_intent: UserIntent;
  task_plan: TaskPlan | null;
  plan: {
    summary: string;
    steps: PlanStep[];
    reasons: string[];
  };
  route: RoutePlan;
  timeline: TimelineData;
  actions: ActionResult[];
  preference_explanation: string[];
  decision_explanation: {
    selected_reasons: string[];
    rejected_reasons: Array<{ name: string; reason: string }>;
    preference_explanation: string[];
    public_reasoning: string;
  } | null;
  composition: {
    summary: string;
    timeline_explanation: string;
    share_message: string;
  } | null;
  planning_warnings: string[];
  exceptions: PlanException[];
  replan_proposals: ReplanProposal[];
  natural_language: string;
}

export interface PlanEvent {
  type: 'progress' | 'result' | 'error';
  stage: string;
  message: string;
  data: Record<string, unknown>;
  source: 'system' | 'deepseek' | 'amap' | 'mock';
}

export async function createPlan(query: string): Promise<PlanResponse> {
  const response = await fetch(`${API_BASE}/api/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function confirmReplan(
  currentPlan: PlanResponse,
  proposalId: string,
  optionId: string,
): Promise<PlanResponse> {
  return requestJson('/api/replan/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      current_plan: currentPlan,
      proposal_id: proposalId,
      option_id: optionId,
    }),
  });
}

export async function getDefaultPreferences(): Promise<PreferenceSetupData> {
  return requestJson('/api/preferences/default');
}

export async function getRuntimeMode(): Promise<RuntimeMode> {
  return requestJson('/api/runtime');
}

export async function getCurrentPreferences(): Promise<PreferenceProfile> {
  return requestJson('/api/preferences/current');
}

export async function savePreferences(
  preference: UserPreference,
): Promise<PreferenceProfile> {
  return requestJson('/api/preferences', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(preference),
  });
}

export async function createPlanStream(
  query: string,
  onEvent: (event: PlanEvent) => void,
): Promise<PlanResponse> {
  const response = await fetch(`${API_BASE}/api/plan/stream`, {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  if (!response.body) {
    throw new Error('浏览器不支持流式响应');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result: PlanResponse | null = null;

  const consumeBlock = (block: string) => {
    const payload = block
      .split(/\r?\n/)
      .filter(line => line.startsWith('data:'))
      .map(line => line.slice(5).trimStart())
      .join('\n');
    if (!payload) return;

    const event = JSON.parse(payload) as PlanEvent;
    onEvent(event);
    if (event.type === 'error') {
      throw new Error(event.message || '流式规划失败');
    }
    if (event.type === 'result') {
      result = event.data as unknown as PlanResponse;
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? '';
    blocks.forEach(consumeBlock);
    if (done) break;
  }
  if (buffer.trim()) {
    consumeBlock(buffer);
  }
  if (!result) {
    throw new Error('流式响应未返回最终方案');
  }
  return result;
}

async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response.json();
}
