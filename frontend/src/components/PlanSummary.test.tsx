// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import type { PlanResponse } from '../api';
import PlanSummary from './PlanSummary';


afterEach(cleanup);


describe('PlanSummary', () => {
  it('does not render identical plan and composition summaries twice', () => {
    const result = {
      user_intent: {
        raw_query: '测试',
        scene: 'family',
        time_window: '今天下午',
        time_windows: [],
        tasks: [],
        duration_hours: [],
        companions: [],
        party_size: 1,
        child_age: null,
        gender_mix: null,
        distance_preference: 'normal',
        activity_preferences: [],
        diet_preferences: [],
        budget_preference: 'normal',
        avoid: [],
        weather_constraint: null,
        city: null,
      },
      task_plan: null,
      plan: {
        summary: '下午亲子轻松出行方案',
        steps: [],
        reasons: [],
      },
      timeline: {
        items: [],
        total_duration_minutes: 180,
      },
      route: {
        origin: {
          name: '起点',
          lat: 31.2,
          lng: 121.4,
        },
        total_travel_minutes: 22,
        stops: [],
        return_to_origin_minutes: 0,
        transport: 'taxi',
        source: 'mock',
        polyline: [],
      },
      actions: [],
      preference_explanation: [],
      decision_explanation: null,
      composition: {
        summary: '下午亲子轻松出行方案',
        timeline_explanation: '',
        share_message: '',
      },
      planning_warnings: [],
      exceptions: [],
      replan_proposals: [],
      natural_language: '下午亲子轻松出行方案',
    } satisfies PlanResponse;

    render(<PlanSummary result={result} />);

    expect(screen.getAllByText('下午亲子轻松出行方案')).toHaveLength(1);
  });
});
