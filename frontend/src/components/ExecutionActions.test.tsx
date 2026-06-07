// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ExecutionActions from './ExecutionActions';


vi.mock('./ActionStatusCard', () => ({
  default: () => <div>动作结果</div>,
}));


afterEach(cleanup);


describe('ExecutionActions', () => {
  it('describes confirmation as revealing prepared mock results', () => {
    render(
      <ExecutionActions
        actions={[]}
        confirmed={false}
        onConfirm={() => undefined}
      />,
    );

    expect(
      screen.getByText('确认后查看点餐、预约和消息生成的模拟结果。'),
    ).toBeTruthy();
    expect(screen.queryByText(/确认后执行/)).toBeNull();
  });
});
