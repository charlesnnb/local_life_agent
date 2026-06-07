import { beforeEach, describe, expect, it, vi } from 'vitest';


const loaderMock = vi.hoisted(() => ({
  load: vi.fn(),
}));

vi.mock('@amap/amap-jsapi-loader', () => ({
  load: loaderMock.load,
}));


describe('loadAMap', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    loaderMock.load.mockResolvedValue({ Map: vi.fn() });
  });

  it('shares one AMap loader promise across duplicate initialization', async () => {
    const { loadAMap } = await import('./amapLoader');
    const options = {
      key: 'test-js-key',
      version: '2.0' as const,
      plugins: ['AMap.Scale', 'AMap.ToolBar'],
    };

    const first = loadAMap(options);
    const second = loadAMap(options);

    expect(first).toBe(second);
    await expect(first).resolves.toEqual({ Map: expect.any(Function) });
    expect(loaderMock.load).toHaveBeenCalledTimes(1);
    expect(loaderMock.load).toHaveBeenCalledWith(options);
  });
});
