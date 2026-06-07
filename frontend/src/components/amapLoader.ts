interface AMapLoadOptions {
  key: string;
  version: '2.0';
  plugins: string[];
}

let loaderPromise: Promise<unknown> | null = null;


export function loadAMap(options: AMapLoadOptions): Promise<unknown> {
  if (!loaderPromise) {
    loaderPromise = import('@amap/amap-jsapi-loader')
      .then(({ load }) => load(options))
      .catch(error => {
        loaderPromise = null;
        throw error;
      });
  }

  return loaderPromise;
}
