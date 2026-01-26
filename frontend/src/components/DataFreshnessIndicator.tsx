import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { queryKeys } from '../api/hooks';

interface DataStatus {
  system_status?: string;
  system_message?: string;
  data_source?: string;
  nordic_momentum?: {
    stocks_count: number;
    last_updated: string | null;
    age_days: number;
  };
  summary?: {
    total_stocks: number;
    fresh_count: number;
    fresh_percentage: number;
  };
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

function formatAbsoluteTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('sv-SE', { 
    month: 'short', 
    day: 'numeric', 
    hour: '2-digit', 
    minute: '2-digit' 
  });
}

// Status icons as simple SVG components for accessibility
const StatusIcon = ({ status }: { status: 'ok' | 'warning' | 'error' }) => {
  if (status === 'ok') {
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
        <circle cx="7" cy="7" r="6" fill="#22c55e" />
        <path d="M4 7l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (status === 'warning') {
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
        <circle cx="7" cy="7" r="6" fill="#f59e0b" />
        <path d="M7 4v3M7 9v.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="6" fill="#ef4444" />
      <path d="M5 5l4 4M9 5l-4 4" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
};

export default function DataFreshnessIndicator() {
  const [showDetails, setShowDetails] = useState(false);

  const { data: status } = useQuery({
    queryKey: queryKeys.data.status(),
    queryFn: () => api.get<DataStatus>('/data/status/detailed'),
    staleTime: 60 * 1000,
  });

  if (!status?.nordic_momentum) return null;

  const { stocks_count, last_updated, age_days } = status.nordic_momentum;
  const iconStatus = age_days <= 1 ? 'ok' : age_days <= 3 ? 'warning' : 'error';
  const statusLabel = age_days <= 1 ? 'Fresh' : age_days <= 3 ? 'Recent' : 'Stale';
  const color = age_days <= 1 ? '#22c55e' : age_days <= 3 ? '#f59e0b' : '#ef4444';

  const lastSyncRelative = last_updated ? formatTimeAgo(last_updated) : 'Never';
  const lastSyncAbsolute = last_updated ? formatAbsoluteTime(last_updated) : 'Never';

  return (
    <div style={{ position: 'relative' }}>
      <button 
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '0.4rem', 
          fontSize: '0.75rem', 
          color: '#666',
          cursor: 'pointer',
          background: 'none',
          border: 'none',
          padding: '0.25rem 0.5rem',
          borderRadius: '0.25rem',
          transition: 'background-color 0.15s'
        }}
        onClick={() => setShowDetails(!showDetails)}
        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f3f4f6'}
        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
        aria-expanded={showDetails}
        aria-label={`Data status: ${statusLabel}. ${stocks_count} stocks. Last updated ${lastSyncRelative}. Click for details.`}
        title={`${stocks_count} stocks · TradingView\nLast update: ${lastSyncAbsolute}`}
      >
        <StatusIcon status={iconStatus} />
        <span>
          {statusLabel} · {lastSyncRelative}
        </span>
      </button>

      {showDetails && (
        <>
          <div 
            style={{ position: 'fixed', inset: 0, zIndex: 40 }} 
            onClick={() => setShowDetails(false)}
            aria-hidden="true"
          />
          <div 
            role="dialog"
            aria-label="Data status details"
            style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: '0.5rem',
              padding: '0.875rem',
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '0.5rem',
              boxShadow: '0 4px 12px -2px rgba(0,0,0,0.12)',
              fontSize: '0.8rem',
              minWidth: '240px',
              zIndex: 50
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: '0.625rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <StatusIcon status={iconStatus} />
              Nordic Momentum Data
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Source</span>
                <span style={{ fontWeight: 500 }}>{status.data_source || 'TradingView'}</span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Stocks</span>
                <span style={{ fontWeight: 500 }}>{stocks_count}</span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Last updated</span>
                <span style={{ fontWeight: 500 }} title={lastSyncAbsolute}>{lastSyncRelative}</span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Status</span>
                <span style={{ fontWeight: 500, color }}>{status.system_message || statusLabel}</span>
              </div>
            </div>

            {age_days > 1 && (
              <div style={{ 
                marginTop: '0.625rem', 
                padding: '0.5rem', 
                backgroundColor: '#fef3c7', 
                borderRadius: '0.25rem',
                fontSize: '0.75rem',
                color: '#92400e'
              }}>
                Data is {age_days} days old. Refresh will happen automatically.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
