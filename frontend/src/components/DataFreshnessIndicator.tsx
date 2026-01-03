import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { queryKeys } from '../api/hooks';

interface DataStatus {
  summary?: {
    total_stocks: number;
    fresh_count: number;
    stale_count: number;
    very_stale_count: number;
    fresh_percentage: number;
  };
}

interface SyncHistory {
  last_successful_sync: string | null;
  next_scheduled_sync: string;
  total_syncs: number;
  successful_syncs: number;
  failed_syncs: number;
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

function formatTimeUntil(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);

  if (diffMins < 1) return 'now';
  if (diffMins < 60) return `in ${diffMins}m`;
  return `in ${diffHours}h ${diffMins % 60}m`;
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

  const { data: syncHistory } = useQuery({
    queryKey: queryKeys.data.syncHistory(1),
    queryFn: () => api.get<SyncHistory>('/data/sync-history?days=1'),
    staleTime: 60 * 1000,
  });

  if (!status?.summary) return null;

  const { fresh_percentage, total_stocks, fresh_count } = status.summary;
  const iconStatus = fresh_percentage >= 80 ? 'ok' : fresh_percentage >= 50 ? 'warning' : 'error';
  const statusLabel = fresh_percentage >= 80 ? 'OK' : fresh_percentage >= 50 ? 'Stale' : 'Outdated';
  const color = fresh_percentage >= 80 ? '#22c55e' : fresh_percentage >= 50 ? '#f59e0b' : '#ef4444';

  const lastSync = syncHistory?.last_successful_sync;
  const nextSync = syncHistory?.next_scheduled_sync;
  const lastSyncRelative = lastSync ? formatTimeAgo(lastSync) : 'Never';
  const lastSyncAbsolute = lastSync ? formatAbsoluteTime(lastSync) : 'Never';

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
        aria-label={`Data status: ${statusLabel}. ${fresh_count} of ${total_stocks} stocks fresh. Last synced ${lastSyncRelative}. Click for details.`}
        title={`${fresh_count}/${total_stocks} stocks (${fresh_percentage.toFixed(0)}%)\nLast sync: ${lastSyncAbsolute}`}
      >
        <StatusIcon status={iconStatus} />
        <span>
          Data {statusLabel} · {lastSyncRelative}
        </span>
      </button>

      {showDetails && (
        <>
          {/* Backdrop to close on click outside */}
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
              Data {statusLabel}
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Coverage</span>
                <span style={{ fontWeight: 500, color }}>{fresh_count}/{total_stocks} ({fresh_percentage.toFixed(0)}%)</span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Last sync</span>
                <span style={{ fontWeight: 500 }} title={lastSyncAbsolute}>{lastSyncRelative}</span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Next sync</span>
                <span style={{ fontWeight: 500 }}>{nextSync ? formatTimeUntil(nextSync) : '—'}</span>
              </div>
              
              {syncHistory && syncHistory.total_syncs > 0 && (
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  marginTop: '0.375rem', 
                  paddingTop: '0.375rem', 
                  borderTop: '1px solid #e5e7eb' 
                }}>
                  <span style={{ color: '#6b7280' }}>24h syncs</span>
                  <span style={{ fontWeight: 500 }}>
                    {syncHistory.successful_syncs}/{syncHistory.total_syncs} OK
                  </span>
                </div>
              )}
            </div>

            {fresh_percentage < 80 && (
              <div style={{ 
                marginTop: '0.625rem', 
                padding: '0.5rem', 
                backgroundColor: '#fef3c7', 
                borderRadius: '0.25rem',
                fontSize: '0.75rem',
                color: '#92400e'
              }}>
                Data may be outdated. Check Data Management for details.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
