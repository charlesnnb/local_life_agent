import React, { useState } from 'react';

interface Props {
  message: string;
}

const ShareMessageBox: React.FC<Props> = ({ message }) => {
  const [copied, setCopied] = useState(false);

  if (!message) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const ta = document.createElement('textarea');
      ta.value = message;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <span>💬</span> 可转发消息
      </h3>
      <div className="relative">
        <div className="p-4 bg-green-50 border border-green-100 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <span className="badge badge-green">微信</span>
            <span className="badge badge-blue">可复制</span>
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">{message}</p>
        </div>
        <button
          onClick={handleCopy}
          className="mt-3 px-4 py-2 text-xs font-medium bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          {copied ? '已复制 ✓' : '复制消息'}
        </button>
      </div>
    </div>
  );
};

export default ShareMessageBox;
