import { Link, useLocation } from 'react-router-dom';

import type { RuntimeMode } from '../api';
import RuntimeModeBadge from './RuntimeModeBadge';


interface HeaderProps {
  runtime: RuntimeMode;
}


export default function Header({ runtime }: HeaderProps) {
  const location = useLocation();
  const onSettings = location.pathname === '/settings';

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/90 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <Link to="/" className="group min-w-0 no-underline">
          <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-blue-600">
            Local Life Agent
          </p>
          <p className="truncate text-lg font-bold text-slate-950 transition group-hover:text-blue-700">
            把想法变成可执行行程
          </p>
        </Link>

        <div className="flex flex-wrap items-center justify-end gap-2">
          <RuntimeModeBadge runtime={runtime} result={null} compact />
          <Link
            to={onSettings ? '/' : '/settings'}
            aria-label={onSettings ? '返回规划页' : '设置偏好'}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
          >
            {onSettings ? <BackIcon /> : <SettingsIcon />}
            <span className="hidden sm:inline">
              {onSettings ? '返回规划' : '偏好设置'}
            </span>
          </Link>
        </div>
      </div>
    </header>
  );
}


function SettingsIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </svg>
  );
}


function BackIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}
