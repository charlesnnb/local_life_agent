import React from 'react';

interface TraceItem {
  phase: string;
  message: string;
}

interface Props {
  trace: TraceItem[];
}

const PHASE_ICONS: Record<string, string> = {
  init: '🚀',
  intent_parsing: '🔍',
  constraint_extraction: '📋',
  candidate_retrieval: '🔎',
  fallback: '⚠️',
  feasibility_check: '✅',
  itinerary_construction: '📅',
  execution: '⚡',
  response: '📤',
};

const AgentTracePanel: React.FC<Props> = ({ trace }) => {
  if (!trace || trace.length === 0) return null;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <span>🧠</span> Agent Planning Trace
      </h3>
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {trace.map((item, i) => (
          <div key={i} className="flex items-start gap-2 text-xs">
            <span className="mt-0.5 flex-shrink-0">{PHASE_ICONS[item.phase] || '•'}</span>
            <span className="text-gray-500 w-24 flex-shrink-0 capitalize">
              {item.phase.replace(/_/g, ' ')}
            </span>
            <span className="text-gray-700">{item.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AgentTracePanel;
