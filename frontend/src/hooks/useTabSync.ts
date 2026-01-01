import { useEffect, useCallback } from 'react';

const CHANNEL_NAME = 'borslabbet-sync';

type SyncMessage = {
  type: 'AUTH_CHANGE' | 'PORTFOLIO_UPDATE' | 'SETTINGS_CHANGE';
  payload?: unknown;
  timestamp: number;
};

/**
 * Hook for syncing state across browser tabs using BroadcastChannel.
 */
export function useTabSync(
  onMessage: (msg: SyncMessage) => void
) {
  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return;
    
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.onmessage = (e) => onMessage(e.data);
    
    return () => channel.close();
  }, [onMessage]);

  const broadcast = useCallback((type: SyncMessage['type'], payload?: unknown) => {
    if (typeof BroadcastChannel === 'undefined') return;
    
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.postMessage({ type, payload, timestamp: Date.now() });
    channel.close();
  }, []);

  return { broadcast };
}
