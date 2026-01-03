import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { queryKeys } from '../api/hooks';
import styles from '../styles/App.module.css';

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

export default function DataFreshnessIndicator() {
  const [showDetails, setShowDetails] = useState(false);

  const { data: status } = useQuery({
    queryKey: queryKeys.data.status(),
    queryFn: () => api.get<DataStatus>('/data/status/detailed'),
    staleTime: 60 * 1000, // 1 min
  });

  const { data: syncHistory } = useQuery({
    queryKey: queryKeys.data.syncHistory(1),
    queryFn: () => api.get<SyncHistory>('/data/sync-history?days=1'),
    staleTime: 60 * 1000, // 1 min
  });

  if (!status?.summary) return null;

  const { fresh_percentage, total_stocks } = status.summary;
  const color = fresh_percentage >= 80 ? '#22c55e' : fresh_percentage >= 50 ? '#f59e0b' : '#ef4444';
  const label = fresh_percentage >= 80 ? 'Fresh' : fresh_percentage >= 50 ? 'Stale' : 'Outdated';

  const lastSync = syncHistory?.last_successful_sync;
  const nextSync = syncHistory?.next_scheduled_sync;

  return (
    <div style={{ position: 'relative' }}>
      <div 
        className={styles.freshnessIndicator} 
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '0.5rem', 
          fontSize: '0.75rem', 
          color: '#666',
          cursor: 'pointer'
        }}
        onClick={() => setShowDetails(!showDetails)}
        title="Click for details"
      >
        <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: color }} />
        <span>
          {label} • {lastSync ? formatTimeAgo(lastSync) : 'No sync'}
        </span>
      </div>

      {showDetails && (
        <div style={{
          position: 'absolute',
          top: '100%',
          right: 0,
          marginTop: '0.5rem',
          padding: '0.75rem',
          backgroundColor: 'white',
          border: '1px solid #e5e7eb',
          borderRadius: '0.5rem',
          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
          fontSize: '0.75rem',
          minWidth: '200px',
          zIndex: 50
        }}>
          <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Data Status</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Stocks:</span>
              <span>{total_stocks}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Fresh:</span>
              <span style={{ color }}>{fresh_percentage.toFixed(0)}%</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Last sync:</span>
              <span>{lastSync ? formatTimeAgo(lastSync) : 'Never'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Next sync:</span>
              <span>{nextSync ? formatTimeUntil(nextSync) : 'Unknown'}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
