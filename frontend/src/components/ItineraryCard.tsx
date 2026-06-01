import React from 'react';

interface ItineraryItem {
  time_start: string;
  time_end: string;
  type: string;
  title: string;
  description: string;
  location_id: string | null;
}

interface Props {
  itinerary: ItineraryItem[];
}

const TYPE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  travel: { bg: 'bg-blue-50 border-blue-200', text: 'text-blue-700', label: '出行' },
  activity: { bg: 'bg-purple-50 border-purple-200', text: 'text-purple-700', label: '活动' },
  meal: { bg: 'bg-orange-50 border-orange-200', text: 'text-orange-700', label: '用餐' },
  extra: { bg: 'bg-pink-50 border-pink-200', text: 'text-pink-700', label: '额外' },
  return: { bg: 'bg-green-50 border-green-200', text: 'text-green-700', label: '返程' },
};

const ItineraryCard: React.FC<Props> = ({ itinerary }) => {
  if (!itinerary || itinerary.length === 0) return null;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <span>🗺️</span> 行程路线
      </h3>
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-[19px] top-2 bottom-2 w-0.5 bg-gray-200" />

        <div className="space-y-3">
          {itinerary.map((item, i) => {
            const style = TYPE_STYLES[item.type] || TYPE_STYLES.activity;
            return (
              <div key={i} className="flex items-start gap-3 relative">
                {/* Timeline dot */}
                <div className={`relative z-10 w-5 h-5 rounded-full border-2 flex-shrink-0 ${style.bg} ${style.text} flex items-center justify-center`}>
                  <div className="w-2 h-2 rounded-full bg-current" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-gray-500">{item.time_start}</span>
                    <span className={`badge text-xs ${style.bg} ${style.text}`}>{style.label}</span>
                  </div>
                  <p className="text-sm font-medium text-gray-800 mt-0.5">{item.title}</p>
                  <p className="text-xs text-gray-500">{item.description}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ItineraryCard;
