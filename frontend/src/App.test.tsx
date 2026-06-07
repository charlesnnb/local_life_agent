// @vitest-environment jsdom

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  PlanResponse,
  PreferenceSetupData,
  UserPreference,
} from './api';
import App, { getDefaultRuntime } from './App';


const apiMocks = vi.hoisted(() => ({
  createPlan: vi.fn(),
  createPlanStream: vi.fn(),
  confirmReplan: vi.fn(),
  getRuntimeMode: vi.fn(),
  getDefaultPreferences: vi.fn(),
  getCurrentPreferences: vi.fn(),
  savePreferences: vi.fn(),
}));

vi.mock('./api', async importOriginal => {
  const original = await importOriginal<typeof import('./api')>();
  return {
    ...original,
    createPlan: apiMocks.createPlan,
    createPlanStream: apiMocks.createPlanStream,
    confirmReplan: apiMocks.confirmReplan,
    getRuntimeMode: apiMocks.getRuntimeMode,
    getDefaultPreferences: apiMocks.getDefaultPreferences,
    getCurrentPreferences: apiMocks.getCurrentPreferences,
    savePreferences: apiMocks.savePreferences,
  };
});

vi.mock('./components/AgentProgress', () => ({
  default: () => null,
}));

vi.mock('./components/Timeline', () => ({
  default: () => null,
}));


const result: PlanResponse = {
  user_intent: {
    raw_query: '测试',
    scene: 'friends',
    time_window: '今天下午',
    time_windows: ['下午'],
    tasks: [],
    duration_hours: [3, 4],
    companions: ['朋友'],
    party_size: 4,
    child_age: null,
    gender_mix: { male: 2, female: 2 },
    distance_preference: 'nearby',
    activity_preferences: [],
    diet_preferences: [],
    budget_preference: 'normal',
    avoid: [],
    weather_constraint: null,
    city: '上海',
  },
  task_plan: null,
  plan: {
    summary: '测试计划',
    steps: [],
    reasons: [],
  },
  route: {
    origin: { name: '起点', lat: 31.18, lng: 121.43 },
    stops: [],
    return_to_origin_minutes: 0,
    total_travel_minutes: 0,
    transport: 'taxi',
    source: 'mock',
    polyline: [],
  },
  timeline: {
    items: [],
    total_duration_minutes: 0,
  },
  actions: [
    {
      type: 'reservation',
      target: '测试餐厅',
      status: 'mock_failed',
      message: 'Mock 数据中没有可用餐位。',
      details: {
        reason: '当前时段已满',
        suggestion: '建议现场取号',
      },
    },
    {
      type: 'food_order',
      target: '肯德基',
      status: 'mock_success',
      message: '已模拟下单。',
      details: {},
    },
    {
      type: 'send_message',
      target: '朋友',
      status: 'mock_success',
      message: '下午三点出发，先去看展，晚上一起吃饭。',
      details: {},
    },
  ],
  preference_explanation: [],
  decision_explanation: null,
  composition: null,
  planning_warnings: [],
  exceptions: [
    {
      exception_id: 'exception_1',
      exception_type: 'restaurant_full',
      source_task_id: 'task_2',
      severity: 'high',
      title: '首选餐厅当前无可预约座位',
      message: '预计到达时段暂无可预约座位',
      impact: {
        mock: true,
        summary: '原餐厅预计等待 70 分钟。',
      },
      status: 'detected',
    },
  ],
  replan_proposals: [
    {
      proposal_id: 'proposal_1',
      exception: {
        exception_id: 'exception_1',
        exception_type: 'restaurant_full',
        source_task_id: 'task_2',
        severity: 'high',
        title: '首选餐厅当前无可预约座位',
        message: '预计到达时段暂无可预约座位',
        impact: {
          mock: true,
          summary: '原餐厅预计等待 70 分钟。',
        },
        status: 'detected',
      },
      options: [
        {
          option_id: 'option_a',
          title: '切换到附近低等待餐厅',
          description: '改去海底捞徐家汇店。',
          changes: ['更新路线与时间线'],
          estimated_delay_minutes: 0,
          estimated_saved_minutes: 60,
          replacement_place: { name: '海底捞徐家汇店' },
          operation: 'replace_restaurant',
          original_plan: { name: '测试餐厅', wait_time_min: 70 },
          proposed_plan: { name: '海底捞徐家汇店', wait_time_min: 10 },
          metadata: {},
        },
        {
          option_id: 'option_keep',
          title: '保持原计划',
          description: '不修改当前计划。',
          changes: ['保留风险提醒'],
          estimated_delay_minutes: 0,
          estimated_saved_minutes: 0,
          replacement_place: null,
          operation: 'keep_original',
          original_plan: { name: '测试餐厅' },
          proposed_plan: { name: '保留原计划' },
          metadata: {},
        },
      ],
      requires_consent: true,
      status: 'pending',
      selected_option_id: null,
    },
  ],
  natural_language: '测试',
};

const preference: UserPreference = {
  activity_types: ['亲子乐园', '展览'],
  max_travel_minutes: 30,
  dining_preferences: ['清淡健康', '亲子友好'],
  activity_intensity: 'light',
  budget_level: 'medium',
  prefer_indoor: false,
  prefer_low_wait: true,
};

const preferenceSetup: PreferenceSetupData = {
  preference,
  weights: {
    distance_weight: 1,
    activity_match_weight: 1,
    child_friendly_weight: 1,
    diet_match_weight: 1,
    popularity_weight: 1,
    budget_weight: 1,
    indoor_weight: 1,
    low_wait_weight: 1,
  },
  options: {
    activity_types: [
      '亲子乐园',
      '展览',
      'Citywalk',
      '商场轻松逛',
      '户外公园',
      '酒吧 / 夜生活',
    ],
    max_travel_minutes: [15, 30, 45],
    dining_preferences: [
      '清淡健康',
      '亲子友好',
      '网红打卡',
      '性价比',
      '火锅烧烤',
    ],
    activity_intensity: ['light', 'medium', 'high'],
    budget_level: ['low', 'medium', 'high'],
  },
};

function renderApp(initialEntries = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <App />
    </MemoryRouter>,
  );
}

function createStorage() {
  const values = new Map<string, string>();
  return {
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => [...values.keys()][index] ?? null,
    get length() {
      return values.size;
    },
    removeItem: (key: string) => values.delete(key),
    setItem: (key: string, value: string) => values.set(key, String(value)),
  };
}


describe('App action status rendering', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', createStorage());
    vi.stubGlobal('sessionStorage', createStorage());
    apiMocks.createPlanStream.mockReset();
    apiMocks.createPlanStream.mockResolvedValue(result);
    apiMocks.confirmReplan.mockReset();
    apiMocks.confirmReplan.mockResolvedValue({
      ...result,
      replan_proposals: [
        {
          ...result.replan_proposals[0],
          status: 'accepted',
          selected_option_id: 'option_a',
        },
      ],
    });
    apiMocks.getRuntimeMode.mockReset();
    apiMocks.getRuntimeMode.mockResolvedValue({
      mode: 'demo',
      llm: 'mock',
      amap: 'mock',
      actions: 'mock',
    });
    apiMocks.getDefaultPreferences.mockReset();
    apiMocks.getDefaultPreferences.mockResolvedValue(preferenceSetup);
    apiMocks.getCurrentPreferences.mockReset();
    apiMocks.getCurrentPreferences.mockResolvedValue({
      preference,
      weights: preferenceSetup.weights,
    });
    apiMocks.savePreferences.mockReset();
    apiMocks.savePreferences.mockResolvedValue({
      preference,
      weights: preferenceSetup.weights,
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('shows mock failures as failures and preserves their explanation', async () => {
    renderApp();

    fireEvent.click(screen.getByRole('button', { name: '开始规划' }));

    expect(
      await screen.findByRole('button', { name: /确认这个计划/ }),
    ).toBeTruthy();
    expect(screen.queryByText('餐厅预约 · 模拟失败')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /确认这个计划/ }));

    expect(
      await screen.findByText('餐厅预约 · 模拟失败'),
    ).toBeTruthy();
    expect(screen.queryByText('餐厅预约 · 成功')).toBeNull();
    expect(screen.getByText('Mock 数据中没有可用餐位。')).toBeTruthy();
    expect(screen.getByText('当前时段已满')).toBeTruthy();
    expect(screen.getByText('建议现场取号')).toBeTruthy();
    expect(screen.getByText('外卖点餐 · 模拟成功')).toBeTruthy();
  });

  it('shows the current demo runtime mode', () => {
    renderApp();

    expect(screen.getByText('Demo Mode')).toBeTruthy();
    expect(screen.getByText('Mock LLM')).toBeTruthy();
    expect(screen.getByText('Mock AMap')).toBeTruthy();
    expect(screen.getByText('Mock Actions')).toBeTruthy();
  });

  it('shows Hybrid Live Mode with real providers and Mock actions', async () => {
    apiMocks.getRuntimeMode.mockResolvedValue({
      mode: 'hybrid',
      llm: 'deepseek',
      amap: 'amap',
      actions: 'mock',
    });

    renderApp();

    expect(await screen.findByText('Hybrid Live Mode')).toBeTruthy();
    expect(screen.getByText('DeepSeek')).toBeTruthy();
    expect(screen.getByText('AMap')).toBeTruthy();
    expect(screen.getByText('Mock Actions')).toBeTruthy();
  });

  it('shows provider fallback sources without presenting Mock as live data', async () => {
    apiMocks.getRuntimeMode.mockResolvedValue({
      mode: 'hybrid',
      llm: 'deepseek',
      amap: 'amap',
      actions: 'mock',
    });
    apiMocks.createPlanStream.mockImplementation(
      async (_query: string, onEvent: (event: unknown) => void) => {
        onEvent({
          type: 'progress',
          stage: 'api_fallback_triggered',
          message: 'DeepSeek 不可用，已切换规则解析',
          data: {},
          source: 'mock',
        });
        return result;
      },
    );

    renderApp();
    fireEvent.click(screen.getByRole('button', { name: '开始规划' }));

    expect(await screen.findByText(/任务理解 Rule fallback/)).toBeTruthy();
    expect(screen.getByText(/地点与路线 Mock fallback/)).toBeTruthy();
    expect(screen.getByText(/点餐\/预约\/消息 Mock/)).toBeTruthy();
  });

  it('fills the query from a demo scenario without submitting', () => {
    renderApp();

    fireEvent.click(screen.getByRole('button', { name: '多阶段一天' }));

    expect((screen.getByRole('textbox', {
      name: '你的周末或闲时需求',
    }) as HTMLTextAreaElement).value).toBe(
      '今天早上想去公园玩，然后中午点个外卖吃肯德基，'
      + '下午去打台球，晚上去喝茶，夜宵吃个螺蛳粉',
    );
    expect(apiMocks.createPlanStream).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '家庭亲子' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '朋友多人' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '天气室内' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '预约失败/备选' })).toBeTruthy();
  });

  it('confirms a proposal and replaces the displayed full plan', async () => {
    renderApp();
    fireEvent.click(screen.getByRole('button', { name: '开始规划' }));

    expect(
      await screen.findByText('首选餐厅当前无可预约座位'),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '接受方案' }));

    await waitFor(() => {
      expect(apiMocks.confirmReplan).toHaveBeenCalledWith(
        result,
        'proposal_1',
        'option_a',
      );
    });
    expect(await screen.findByText('已接受并更新计划')).toBeTruthy();
  });

  it('opens the four-step preference questionnaire from the settings button', async () => {
    renderApp();

    fireEvent.click(screen.getByRole('link', { name: '设置偏好' }));

    expect(await screen.findByText('步骤 1 / 4')).toBeTruthy();
    expect(screen.getByText('你更喜欢什么活动？')).toBeTruthy();
    expect(screen.queryByText('你的周末或闲时需求')).toBeNull();
  });

  it('saves preferences and returns to the planner page', async () => {
    renderApp(['/settings']);

    expect(await screen.findByText('步骤 1 / 4')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    expect(screen.getByText('步骤 2 / 4')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    expect(screen.getByText('步骤 3 / 4')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    expect(screen.getByText('步骤 4 / 4')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '保存偏好' }));

    await waitFor(() => {
      expect(apiMocks.savePreferences).toHaveBeenCalledWith(preference);
    });
    expect(localStorage.getItem('preference-questionnaire-completed')).toBe('true');
    expect(await screen.findByText('一句话，把今天安排好')).toBeTruthy();
  });

  it('dismisses the first-use preference prompt for the browser session', async () => {
    const firstRender = renderApp();

    expect(
      await screen.findByText('用 1 分钟告诉 Agent 你的偏好'),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '稍后再说' }));
    expect(
      screen.queryByText('用 1 分钟告诉 Agent 你的偏好'),
    ).toBeNull();

    firstRender.unmount();
    renderApp();

    expect(
      screen.queryByText('用 1 分钟告诉 Agent 你的偏好'),
    ).toBeNull();
    expect(sessionStorage.getItem('preference-prompt-dismissed')).toBe('true');
  });

  it('shows only a compact preference summary on the planner page', async () => {
    localStorage.setItem('preference-questionnaire-completed', 'true');
    renderApp();

    expect(await screen.findByText(/当前偏好：/)).toBeTruthy();
    expect(screen.getByText(/轻松/)).toBeTruthy();
    expect(screen.getByText(/30 分钟内/)).toBeTruthy();
    expect(screen.queryByText('更喜欢哪些活动？')).toBeNull();
  });

  it('copies the share message and shows concise feedback', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', {
      ...navigator,
      clipboard: { writeText },
    });
    renderApp();

    fireEvent.click(screen.getByRole('button', { name: '开始规划' }));
    expect(await screen.findByText('分享计划')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '复制计划' }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(
        '下午三点出发，先去看展，晚上一起吃饭。',
      );
    });
    expect(screen.getByText('已复制')).toBeTruthy();
  });
});


describe('runtime bootstrap', () => {
  it('uses the Vite profile before backend runtime metadata arrives', () => {
    expect(getDefaultRuntime('hybrid')).toEqual({
      mode: 'hybrid',
      llm: 'deepseek',
      amap: 'amap',
      actions: 'mock',
    });
    expect(getDefaultRuntime('live')).toEqual({
      mode: 'live',
      llm: 'deepseek',
      amap: 'amap',
      actions: 'mock_fallback',
    });
    expect(getDefaultRuntime('test').mode).toBe('demo');
  });
});
