import React from 'react';

interface SyncMethodSelectorProps {
  selectedMethod: string;
  onMethodChange: (method: string) => void;
  disabled?: boolean;
}

const SyncMethodSelector: React.FC<SyncMethodSelectorProps> = ({
  selectedMethod,
  onMethodChange,
  disabled = false
}) => {
  const methods = [
    {
      value: 'twelvedata',
      label: 'TwelveData FREE',
      description: '800 calls/day, real fundamentals (COMPLETELY FREE)',
      recommended: true
    },
    {
      value: 'hybrid',
      label: 'Hybrid Static',
      description: 'Static fundamentals + estimated prices (instant)',
      recommended: false
    },
    {
      value: 'comprehensive',
      label: 'Web Scraping',
      description: 'Full scraping (may be blocked)',
      recommended: false
    },
    {
      value: 'optimized',
      label: 'Yahoo (Slow)',
      description: 'Fallback option, very slow',
      recommended: false
    }
  ];

  return (
    <div className="sync-method-selector">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Sync Method
      </label>
      <div className="space-y-2">
        {methods.map((method) => (
          <div key={method.value} className="flex items-center">
            <input
              id={method.value}
              name="sync-method"
              type="radio"
              value={method.value}
              checked={selectedMethod === method.value}
              onChange={(e) => onMethodChange(e.target.value)}
              disabled={disabled}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
            />
            <label htmlFor={method.value} className="ml-3 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900">
                  {method.label}
                </span>
                {method.recommended && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                    Recommended
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500">{method.description}</p>
            </label>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SyncMethodSelector;
