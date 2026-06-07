// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import type { PlanEvent } from '../api';
import AgentProgress from './AgentProgress';


const events: PlanEvent[] = [
  {
    type: 'progress',
    stage: 'intent_parsing',
    message: '已理解时间、同行人和活动偏好',
    data: {},
    source: 'deepseek',
  },
  {
    type: 'progress',
    stage: 'tool_execution',
    message: '已搜索并选择活动地点',
    data: {
      tool_name: 'poi_tool',
      selected_result: {
        name: '徐家汇体育公园',
        selection_reasons: ['距离合适', '亲子友好'],
      },
      rejected_candidates: [
        { name: '远郊公园', reason: '超出通勤偏好' },
      ],
    },
    source: 'amap',
  },
  {
    type: 'progress',
    stage: 'completed',
    message: '方案生成完成',
    data: {},
    source: 'system',
  },
];


afterEach(cleanup);


describe('AgentProgress', () => {
  it('is collapsed after completion and keeps technical details nested', () => {
    render(<AgentProgress events={events} loading={false} />);

    expect(screen.getByText('Agent 已完成规划')).toBeTruthy();
    expect(screen.getByText('调用 1 个工具 · 共 3 个步骤')).toBeTruthy();
    expect(screen.queryByText('已搜索并选择活动地点')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: '查看执行过程' }));
    expect(screen.getByText('已搜索并选择活动地点')).toBeTruthy();
    expect(screen.queryByText('远郊公园')).toBeNull();

    fireEvent.click(screen.getAllByText('查看技术详情')[1]);
    expect(screen.getByText(/远郊公园/)).toBeTruthy();
    expect(screen.getByText(/超出通勤偏好/)).toBeTruthy();
  });

  it('shows a compact current stage while planning', () => {
    render(<AgentProgress events={events.slice(0, 2)} loading />);

    expect(screen.getByText('正在为你安排今天的计划...')).toBeTruthy();
    expect(screen.getByText('已完成 2 个步骤')).toBeTruthy();
    expect(screen.getByText('已搜索并选择活动地点')).toBeTruthy();
  });

  it('does not display an incorrect zero tool count', () => {
    render(
      <AgentProgress
        loading={false}
        events={[
          {
            type: 'progress',
            stage: 'activity_search',
            message: '正在搜索附近活动',
            data: {},
            source: 'system',
          },
          {
            type: 'progress',
            stage: 'restaurant_search',
            message: '正在筛选餐厅',
            data: {},
            source: 'system',
          },
        ]}
      />,
    );

    expect(screen.queryByText(/调用 0 个工具/)).toBeNull();
    expect(screen.getByText('共完成 2 个规划步骤')).toBeTruthy();
  });

  it('deduplicates adjacent identical progress events', () => {
    render(
      <AgentProgress
        loading={false}
        events={[
          {
            type: 'progress',
            stage: 'completed',
            message: '方案生成完成',
            data: {},
            source: 'system',
          },
          {
            type: 'progress',
            stage: 'completed',
            message: '方案生成完成',
            data: {},
            source: 'system',
          },
        ]}
      />,
    );

    expect(screen.getByText('共完成 1 个规划步骤')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '查看执行过程' }));
    expect(screen.getAllByText('方案生成完成')).toHaveLength(1);
  });
});
