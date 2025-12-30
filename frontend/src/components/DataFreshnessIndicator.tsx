import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { RefreshCw, Clock, AlertTriangle } from 'lucide-react';

interface DataFreshnessProps {
  className?: string;
}

interface DataFreshness {
  last_sync: string | null;
  cache_efficiency: string;
  problem_stocks: number;
  total_stocks: number;
}

const DataFreshnessIndicator: React.FC<DataFreshnessProps> = ({ className = '' }) => {
  const [freshness, setFreshness] = useState<DataFreshness | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchFreshness = async () => {
    try {
      const response = await fetch('/api/data/status/detailed');
      const data = await response.json();
      
      // Find most recent update
      const lastUpdates = data.stock_status
        .filter((s: any) => s.last_updated)
        .map((s: any) => new Date(s.last_updated))
        .sort((a: Date, b: Date) => b.getTime() - a.getTime());
      
      const problemStocks = data.stock_status.filter((s: any) => 
        s.fetch_success === false || !s.has_data
      ).length;

      setFreshness({
        last_sync: lastUpdates[0]?.toISOString() || null,
        cache_efficiency: data.cache_stats.cache_efficiency,
        problem_stocks: problemStocks,
        total_stocks: data.total_stocks
      });
    } catch (error) {
      console.error('Failed to fetch data freshness:', error);
    }
  };

  const triggerRefresh = async () => {
    setRefreshing(true);
    try {
      const response = await fetch('/api/data/sync-now?method=avanza', {
        method: 'POST'
      });
      if (response.ok) {
        // Wait a moment then refresh status
        setTimeout(fetchFreshness, 2000);
      }
    } catch (error) {
      console.error('Failed to trigger refresh:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const formatLastSync = (timestamp: string | null) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));
    
    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}h ago`;
    return date.toLocaleDateString();
  };

  const getStatusColor = () => {
    if (!freshness) return 'secondary';
    if (freshness.problem_stocks > 0) return 'destructive';
    
    const lastSync = freshness.last_sync ? new Date(freshness.last_sync) : null;
    if (!lastSync) return 'secondary';
    
    const ageMinutes = (new Date().getTime() - lastSync.getTime()) / (1000 * 60);
    if (ageMinutes > 60) return 'secondary';
    if (ageMinutes > 30) return 'default';
    return 'default';
  };

  useEffect(() => {
    fetchFreshness();
    // Refresh every 60 seconds
    const interval = setInterval(fetchFreshness, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!freshness) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <Badge variant="secondary">
          <Clock className="w-3 h-3 mr-1" />
          Loading...
        </Badge>
      </div>
    );
  }

  return (
    <div className={`flex items-center space-x-2 ${className}`}>
      <Badge variant={getStatusColor()}>
        <Clock className="w-3 h-3 mr-1" />
        {formatLastSync(freshness.last_sync)}
      </Badge>
      
      {freshness.problem_stocks > 0 && (
        <Badge variant="destructive">
          <AlertTriangle className="w-3 h-3 mr-1" />
          {freshness.problem_stocks} issues
        </Badge>
      )}
      
      <Badge variant="outline">
        Cache: {freshness.cache_efficiency}
      </Badge>
      
      <Button
        size="sm"
        variant="outline"
        onClick={triggerRefresh}
        disabled={refreshing}
      >
        {refreshing ? (
          <RefreshCw className="w-3 h-3 animate-spin" />
        ) : (
          <RefreshCw className="w-3 h-3" />
        )}
      </Button>
    </div>
  );
};

export default DataFreshnessIndicator;
