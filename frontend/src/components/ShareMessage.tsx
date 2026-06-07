import { useEffect, useRef, useState } from 'react';


interface ShareMessageProps {
  message: string;
  personal: boolean;
}


export default function ShareMessage({
  message,
  personal,
}: ShareMessageProps) {
  const [copyStatus, setCopyStatus] = useState('');
  const resetTimer = useRef<number | null>(null);

  useEffect(() => () => {
    if (resetTimer.current !== null) window.clearTimeout(resetTimer.current);
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message);
      setCopyStatus('已复制');
    } catch {
      setCopyStatus('复制失败');
    }
    if (resetTimer.current !== null) window.clearTimeout(resetTimer.current);
    resetTimer.current = window.setTimeout(() => setCopyStatus(''), 1800);
  };

  return (
    <section className="rounded-2xl border border-blue-200 bg-blue-50 p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-600">
            Share
          </p>
          <h3 className="mt-1 font-bold text-blue-950">分享计划</h3>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-blue-900">
            {message}
          </p>
          {personal && (
            <p className="mt-2 text-xs text-blue-700">这是一份个人计划备忘。</p>
          )}
        </div>
        <button
          type="button"
          onClick={copy}
          className="min-h-10 shrink-0 rounded-xl border border-blue-200 bg-white px-4 text-sm font-bold text-blue-700 transition hover:bg-blue-100"
        >
          {copyStatus || '复制计划'}
        </button>
      </div>
    </section>
  );
}
