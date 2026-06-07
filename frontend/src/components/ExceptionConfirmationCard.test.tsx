// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ReplanProposal } from '../api';


const proposal: ReplanProposal = {
  proposal_id: 'proposal_1',
  exception: {
    exception_id: 'exception_1',
    exception_type: 'restaurant_full',
    source_task_id: 'task_2',
    severity: 'high',
    title: '首选餐厅当前无可预约座位',
    message: '蜀大侠火锅 18:00 时段已满，预约操作未执行成功。',
    impact: {
      mock: true,
      summary: '按原计划前往预计需等待 70 分钟，晚间行程可能整体延后。',
    },
    status: 'detected',
  },
  options: [
    {
      option_id: 'option_a',
      title: '切换到附近低等待餐厅',
      description: '海底捞徐家汇店预计等待 10 分钟。',
      changes: ['替换餐厅地点', '重新计算路线与时间线'],
      estimated_delay_minutes: 0,
      estimated_saved_minutes: 60,
      replacement_place: { name: '海底捞徐家汇店' },
      operation: 'replace_restaurant',
      original_plan: {
        name: '蜀大侠火锅',
        wait_time_min: 70,
      },
      proposed_plan: {
        name: '海底捞徐家汇店',
        wait_time_min: 10,
      },
      metadata: {},
    },
    {
      option_id: 'option_keep',
      title: '保持原计划',
      description: '不自动修改当前计划。',
      changes: ['保留风险提醒'],
      estimated_delay_minutes: 0,
      estimated_saved_minutes: 0,
      replacement_place: null,
      operation: 'keep_original',
      original_plan: { name: '蜀大侠火锅' },
      proposed_plan: { name: '保留原计划' },
      metadata: {},
    },
  ],
  requires_consent: true,
  status: 'pending',
  selected_option_id: null,
};


afterEach(cleanup);


describe('ExceptionConfirmationCard', () => {
  it('shows the exception, comparison, time change, and mock boundary', async () => {
    const loaded = await import('./ExceptionConfirmationCard').catch(() => null);
    expect(loaded).not.toBeNull();
    if (!loaded) return;

    render(
      <loaded.default
        proposal={proposal}
        onConfirm={vi.fn()}
        busy={false}
      />,
    );

    expect(screen.getByText('首选餐厅当前无可预约座位')).toBeTruthy();
    expect(screen.getByText('Mock 异常')).toBeTruthy();
    expect(screen.getByText(/预计需等待 70 分钟/)).toBeTruthy();
    expect(screen.getByText('蜀大侠火锅')).toBeTruthy();
    expect(screen.getByText('海底捞徐家汇店')).toBeTruthy();
    expect(screen.getByText('预计节省 60 分钟')).toBeTruthy();
    expect(screen.getByRole('button', { name: '接受方案' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '保持原计划' })).toBeTruthy();
  });

  it('submits the selected alternative or the keep-original option', async () => {
    const loaded = await import('./ExceptionConfirmationCard').catch(() => null);
    expect(loaded).not.toBeNull();
    if (!loaded) return;
    const onConfirm = vi.fn();

    render(
      <loaded.default
        proposal={proposal}
        onConfirm={onConfirm}
        busy={false}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '接受方案' }));
    expect(onConfirm).toHaveBeenCalledWith('option_a');

    fireEvent.click(screen.getByRole('button', { name: '保持原计划' }));
    expect(onConfirm).toHaveBeenCalledWith('option_keep');
  });

  it('shows an explicit message when no qualified alternative exists', async () => {
    const loaded = await import('./ExceptionConfirmationCard').catch(() => null);
    expect(loaded).not.toBeNull();
    if (!loaded) return;
    const noAlternative = {
      ...proposal,
      options: [
        {
          ...proposal.options[1],
          description: '当前没有找到符合条件的替代活动，建议扩大距离或更换活动类型。',
        },
      ],
    };

    render(
      <loaded.default
        proposal={noAlternative}
        onConfirm={vi.fn()}
        busy={false}
      />,
    );

    expect(
      screen.getByText(/当前没有找到符合条件的替代活动/),
    ).toBeTruthy();
  });
});
