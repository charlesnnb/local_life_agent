import React, { useState } from 'react';

interface Props {
  onPlan: (query: string) => void;
  loading: boolean;
}

const FAMILY_EXAMPLE = '今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远，帮我安排一下。';
const FRIENDS_EXAMPLE = '今天下午我们 4 个人，2 男 2 女，想出去玩几个小时，顺便吃饭，别太远。';

const QueryInput: React.FC<Props> = ({ onPlan, loading }) => {
  const [query, setQuery] = useState(FAMILY_EXAMPLE);

  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-2xl">🤖</span>
        <div>
          <h2 className="text-lg font-semibold text-gray-800">告诉 Agent 你的需求</h2>
          <p className="text-sm text-gray-500">用自然语言描述，Agent 会帮你安排一切</p>
        </div>
      </div>

      <textarea
        className="w-full h-24 p-3 border border-gray-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="描述你的下午活动需求..."
      />

      <div className="flex items-center gap-3 mt-3">
        <button
          onClick={() => onPlan(query)}
          disabled={loading || !query.trim()}
          className="px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Agent 规划中...
            </span>
          ) : (
            '开始规划'
          )}
        </button>

        <button
          onClick={() => setQuery(FAMILY_EXAMPLE)}
          className="px-3 py-2 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          家庭场景示例
        </button>
        <button
          onClick={() => setQuery(FRIENDS_EXAMPLE)}
          className="px-3 py-2 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          朋友场景示例
        </button>
      </div>
    </div>
  );
};

export default QueryInput;
