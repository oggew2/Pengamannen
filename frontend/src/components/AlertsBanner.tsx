import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { queryKeys } from '../api/hooks';
import styles from '../styles/App.module.css';

interface Alert {
  type: string;
  message: string;
  priority: string;
  strategy?: string;
  ticker?: string;
  days_until?: number;
}

export function AlertsBanner() {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const { data } = useQuery({
    queryKey: queryKeys.alerts.all,
    queryFn: () => api.get<{ alerts: { alerts: Alert[] } }>('/alerts'),
  });

  const alerts = data?.alerts?.alerts || [];
  const visibleAlerts = alerts.filter(a => !dismissed.has(a.message));
  
  if (!visibleAlerts.length) return null;

  const highPriority = visibleAlerts.filter(a => a.priority === 'high');
  const otherAlerts = visibleAlerts.filter(a => a.priority !== 'high');

  return (
    <div style={{ marginBottom: '1rem' }}>
      {highPriority.map((alert, i) => (
        <div key={i} className={styles.card} style={{ 
          background: 'var(--color-primary)', 
          color: 'white',
          marginBottom: '0.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span style={{ color: '#f59e0b' }}>! {alert.message}</span>
          <button 
            onClick={() => setDismissed(new Set([...dismissed, alert.message]))}
            style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer', fontSize: '1.2rem' }}
          >×</button>
        </div>
      ))}
      
      {otherAlerts.length > 0 && (
        <details className={styles.card} style={{ padding: '0.75rem' }}>
          <summary style={{ cursor: 'pointer' }}>
            🔔 {otherAlerts.length} notification{otherAlerts.length > 1 ? 's' : ''}
          </summary>
          <ul style={{ marginTop: '0.5rem', paddingLeft: '1.5rem', fontSize: '0.875rem' }}>
            {otherAlerts.map((a, i) => (
              <li key={i} style={{ marginBottom: '0.25rem' }}>{a.message}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
