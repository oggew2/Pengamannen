import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, AlertTriangle, CheckCircle, Clock, Settings } from 'lucide-react';

interface StockStatus {
  ticker: string;
  stock_id: string;
  last_updated: string | null;
  fetch_success: boolean | null;
  error: string | null;
  has_data: boolean;
}

interface CacheStats {
  total_entries: number;
  valid_entries: number;
  total_hits: number;
  avg_hits_per_entry: number;
  cache_efficiency: string;
}

interface DataStatus {
  cache_stats: CacheStats;
  stock_status: StockStatus[];
  total_stocks: number;
  checked_stocks: number;
}

const DataManagement: React.FC = () => {
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState<string | null>(null);

  const fetchDataStatus = async () => {
    try {
      const response = await fetch('/api/data/status/detailed');
      const data = await response.json();
      setDataStatus(data);
    } catch (error) {
      console.error('Failed to fetch data status:', error);
    } finally {
      setLoading(false);
    }
  };

  const refreshStock = async (ticker: string) => {
    setRefreshing(ticker);
    try {
      const response = await fetch(`/api/data/refresh-stock/${ticker}`, {
        method: 'POST'
      });
      const result = await response.json();
      
      if (result.success) {
        // Refresh the data status
        await fetchDataStatus();
      } else {
        alert(`Failed to refresh ${ticker}: ${result.error}`);
      }
    } catch (error) {
      alert(`Error refreshing ${ticker}: ${error}`);
    } finally {
      setRefreshing(null);
    }
  };

  const getStatusBadge = (stock: StockStatus) => {
    if (stock.fetch_success === false) {
      return <Badge variant="destructive"><AlertTriangle className="w-3 h-3 mr-1" />Failed</Badge>;
    }
    if (!stock.has_data) {
      return <Badge variant="secondary"><Clock className="w-3 h-3 mr-1" />No Data</Badge>;
    }
    return <Badge variant="default"><CheckCircle className="w-3 h-3 mr-1" />OK</Badge>;
  };

  const formatLastUpdated = (timestamp: string | null) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));
    
    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}h ago`;
    return date.toLocaleDateString();
  };

  useEffect(() => {
    fetchDataStatus();
    // Refresh every 30 seconds
    const interval = setInterval(fetchDataStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <RefreshCw className="w-6 h-6 animate-spin mr-2" />
        Loading data status...
      </div>
    );
  }

  if (!dataStatus) {
    return (
      <div className="p-8 text-center">
        <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-red-500" />
        <p>Failed to load data status</p>
        <Button onClick={fetchDataStatus} className="mt-4">
          <RefreshCw className="w-4 h-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  const problemStocks = dataStatus.stock_status.filter(s => 
    s.fetch_success === false || !s.has_data
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Data Management</h1>
        <Button onClick={fetchDataStatus} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh Status
        </Button>
      </div>

      {/* Cache Statistics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Settings className="w-5 h-5 mr-2" />
            Cache Statistics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {dataStatus.cache_stats.total_entries}
              </div>
              <div className="text-sm text-gray-600">Total Entries</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {dataStatus.cache_stats.valid_entries}
              </div>
              <div className="text-sm text-gray-600">Valid Entries</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {dataStatus.cache_stats.total_hits}
              </div>
              <div className="text-sm text-gray-600">Total Hits</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {dataStatus.cache_stats.avg_hits_per_entry}
              </div>
              <div className="text-sm text-gray-600">Avg Hits/Entry</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-indigo-600">
                {dataStatus.cache_stats.cache_efficiency}
              </div>
              <div className="text-sm text-gray-600">Efficiency</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Problem Stocks Alert */}
      {problemStocks.length > 0 && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="flex items-center text-red-700">
              <AlertTriangle className="w-5 h-5 mr-2" />
              Stocks Requiring Attention ({problemStocks.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2">
              {problemStocks.map((stock) => (
                <div key={stock.ticker} className="flex items-center justify-between p-2 bg-white rounded border">
                  <div className="flex items-center space-x-3">
                    <span className="font-mono font-medium">{stock.ticker}</span>
                    {getStatusBadge(stock)}
                    {stock.error && (
                      <span className="text-sm text-red-600">{stock.error}</span>
                    )}
                  </div>
                  <Button
                    size="sm"
                    onClick={() => refreshStock(stock.ticker)}
                    disabled={refreshing === stock.ticker}
                  >
                    {refreshing === stock.ticker ? (
                      <RefreshCw className="w-3 h-3 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3 h-3" />
                    )}
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* All Stocks Status */}
      <Card>
        <CardHeader>
          <CardTitle>Stock Data Status</CardTitle>
          <p className="text-sm text-gray-600">
            Showing {dataStatus.checked_stocks} of {dataStatus.total_stocks} stocks
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {dataStatus.stock_status.map((stock) => (
              <div key={stock.ticker} className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center space-x-4">
                  <span className="font-mono font-medium w-16">{stock.ticker}</span>
                  {getStatusBadge(stock)}
                  <span className="text-sm text-gray-600">
                    ID: {stock.stock_id}
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <span className="text-sm text-gray-500">
                    {formatLastUpdated(stock.last_updated)}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => refreshStock(stock.ticker)}
                    disabled={refreshing === stock.ticker}
                  >
                    {refreshing === stock.ticker ? (
                      <RefreshCw className="w-3 h-3 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3 h-3" />
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default DataManagement;
