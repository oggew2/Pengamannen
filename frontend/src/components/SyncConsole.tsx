import React, { useState, useEffect, useRef } from 'react';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
  details?: string;
}

interface SyncConsoleProps {
  isOpen: boolean;
  onClose: () => void;
  syncProgress?: {
    current: number;
    total: number;
    status: string;
  };
}

const SyncConsole: React.FC<SyncConsoleProps> = ({ isOpen, onClose, syncProgress }) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (isOpen && !wsRef.current) {
      // Connect to WebSocket for real-time logs
      const ws = new WebSocket(`ws://localhost:8000/ws/sync-logs`);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        addLog('info', 'Connected to sync console');
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        addLog(data.level, data.message, data.details);
      };

      ws.onclose = () => {
        setIsConnected(false);
        addLog('warning', 'Disconnected from sync console');
      };

      ws.onerror = () => {
        setIsConnected(false);
        addLog('error', 'Console connection error');
      };
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [isOpen]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = (level: LogEntry['level'], message: string, details?: string) => {
    setLogs(prev => [...prev, {
      timestamp: new Date().toLocaleTimeString(),
      level,
      message,
      details
    }]);
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'error': return 'text-red-600';
      case 'warning': return 'text-yellow-600';
      case 'success': return 'text-green-600';
      default: return 'text-gray-600';
    }
  };

  const getLevelIcon = (level: LogEntry['level']) => {
    switch (level) {
      case 'error': return '❌';
      case 'warning': return '⚠️';
      case 'success': return '✅';
      default: return 'ℹ️';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-4/5 h-4/5 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold">Sync Console</h3>
            <div className={`flex items-center gap-2 text-sm ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
              {isConnected ? 'Connected' : 'Disconnected'}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={clearLogs}
              className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded"
            >
              Clear
            </button>
            <button
              onClick={onClose}
              className="px-3 py-1 text-sm bg-red-100 hover:bg-red-200 text-red-700 rounded"
            >
              Close
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        {syncProgress && (
          <div className="p-4 border-b bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">
                Progress: {syncProgress.current}/{syncProgress.total} stocks
              </span>
              <span className="text-sm text-gray-600">{syncProgress.status}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${(syncProgress.current / syncProgress.total) * 100}%` }}
              ></div>
            </div>
          </div>
        )}

        {/* Logs */}
        <div className="flex-1 overflow-auto p-4 bg-gray-900 text-green-400 font-mono text-sm">
          {logs.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              No logs yet. Start a sync to see real-time progress.
            </div>
          ) : (
            logs.map((log, index) => (
              <div key={index} className="mb-1">
                <span className="text-gray-400">[{log.timestamp}]</span>
                <span className="ml-2">{getLevelIcon(log.level)}</span>
                <span className={`ml-2 ${getLevelColor(log.level)}`}>
                  {log.message}
                </span>
                {log.details && (
                  <div className="ml-8 text-gray-500 text-xs">
                    {log.details}
                  </div>
                )}
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
};

export default SyncConsole;
