import React from 'react';

interface ToolCall {
  tool_name?: string;
  tool?: string;
  input?: any;
  output?: any;
  success: boolean;
  message: string;
}

interface Props {
  toolCalls: ToolCall[];
}

const ToolCallTimeline: React.FC<Props> = ({ toolCalls }) => {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <span>🔧</span> Tool Call Timeline
      </h3>
      <div className="space-y-3">
        {toolCalls.map((tc, i) => (
          <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
            <span className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-xs flex-shrink-0 ${
              tc.success ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
            }`}>
              {tc.success ? '✓' : '✗'}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-800">{tc.tool_name || tc.tool}</span>
                <span className={`badge ${tc.success ? 'badge-green' : 'badge-red'}`}>
                  {tc.success ? '成功' : '失败'}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1 truncate">{tc.message}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ToolCallTimeline;
