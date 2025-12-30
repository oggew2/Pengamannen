import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Plus, Save, Trash2, Edit, Check, X } from 'lucide-react';

interface StockMapping {
  ticker: string;
  stock_id: string;
}

interface StockConfig {
  known_stocks: Record<string, string>;
  total_mapped: number;
}

const StockConfiguration: React.FC = () => {
  const [config, setConfig] = useState<StockConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [newTicker, setNewTicker] = useState('');
  const [newStockId, setNewStockId] = useState('');
  const [editStockId, setEditStockId] = useState('');

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/data/stock-config');
      const data = await response.json();
      setConfig(data);
    } catch (error) {
      console.error('Failed to fetch stock config:', error);
    } finally {
      setLoading(false);
    }
  };

  const addNewMapping = () => {
    if (!newTicker || !newStockId || !config) return;
    
    const updatedConfig = {
      ...config,
      known_stocks: {
        ...config.known_stocks,
        [newTicker.toUpperCase()]: newStockId
      },
      total_mapped: config.total_mapped + 1
    };
    
    setConfig(updatedConfig);
    setNewTicker('');
    setNewStockId('');
  };

  const startEdit = (ticker: string, stockId: string) => {
    setEditingTicker(ticker);
    setEditStockId(stockId);
  };

  const saveEdit = () => {
    if (!editingTicker || !editStockId || !config) return;
    
    const updatedConfig = {
      ...config,
      known_stocks: {
        ...config.known_stocks,
        [editingTicker]: editStockId
      }
    };
    
    setConfig(updatedConfig);
    setEditingTicker(null);
    setEditStockId('');
  };

  const cancelEdit = () => {
    setEditingTicker(null);
    setEditStockId('');
  };

  const deleteMapping = (ticker: string) => {
    if (!config) return;
    
    const { [ticker]: deleted, ...remainingStocks } = config.known_stocks;
    
    const updatedConfig = {
      ...config,
      known_stocks: remainingStocks,
      total_mapped: config.total_mapped - 1
    };
    
    setConfig(updatedConfig);
  };

  const testStockId = async (stockId: string) => {
    try {
      const response = await fetch(`https://www.avanza.se/_api/market-guide/stock/${stockId}`);
      if (response.ok) {
        const data = await response.json();
        return {
          valid: true,
          name: data.name,
          ticker: data.listing?.tickerSymbol
        };
      }
      return { valid: false, error: `HTTP ${response.status}` };
    } catch (error) {
      return { valid: false, error: 'Network error' };
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  if (loading) {
    return <div className="p-8">Loading stock configuration...</div>;
  }

  if (!config) {
    return <div className="p-8">Failed to load stock configuration</div>;
  }

  const mappings = Object.entries(config.known_stocks).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Stock Configuration</h1>
        <Badge variant="secondary">
          {config.total_mapped} stocks mapped
        </Badge>
      </div>

      {/* Add New Mapping */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Plus className="w-5 h-5 mr-2" />
            Add New Stock Mapping
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex space-x-4">
            <div className="flex-1">
              <label className="block text-sm font-medium mb-1">Ticker</label>
              <Input
                placeholder="e.g., ERIC-B"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
              />
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium mb-1">Avanza Stock ID</label>
              <Input
                placeholder="e.g., 5240"
                value={newStockId}
                onChange={(e) => setNewStockId(e.target.value)}
              />
            </div>
            <div className="flex items-end">
              <Button 
                onClick={addNewMapping}
                disabled={!newTicker || !newStockId}
              >
                <Plus className="w-4 h-4 mr-2" />
                Add
              </Button>
            </div>
          </div>
          <p className="text-sm text-gray-600 mt-2">
            Find Avanza stock IDs by inspecting network requests on avanza.se stock pages
          </p>
        </CardContent>
      </Card>

      {/* Current Mappings */}
      <Card>
        <CardHeader>
          <CardTitle>Current Stock Mappings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {mappings.map(([ticker, stockId]) => (
              <div key={ticker} className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center space-x-4">
                  <span className="font-mono font-medium w-20">{ticker}</span>
                  {editingTicker === ticker ? (
                    <Input
                      value={editStockId}
                      onChange={(e) => setEditStockId(e.target.value)}
                      className="w-24"
                    />
                  ) : (
                    <span className="text-gray-600 w-24">{stockId}</span>
                  )}
                </div>
                <div className="flex items-center space-x-2">
                  {editingTicker === ticker ? (
                    <>
                      <Button size="sm" onClick={saveEdit}>
                        <Check className="w-3 h-3" />
                      </Button>
                      <Button size="sm" variant="outline" onClick={cancelEdit}>
                        <X className="w-3 h-3" />
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={() => startEdit(ticker, stockId)}
                      >
                        <Edit className="w-3 h-3" />
                      </Button>
                      <Button 
                        size="sm" 
                        variant="destructive"
                        onClick={() => deleteMapping(ticker)}
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Instructions */}
      <Card className="bg-blue-50 border-blue-200">
        <CardHeader>
          <CardTitle className="text-blue-800">How to Find Avanza Stock IDs</CardTitle>
        </CardHeader>
        <CardContent className="text-blue-700">
          <ol className="list-decimal list-inside space-y-2">
            <li>Go to avanza.se and search for the stock</li>
            <li>Open the stock's detail page</li>
            <li>Open browser developer tools (F12)</li>
            <li>Go to Network tab and refresh the page</li>
            <li>Look for requests to URLs like <code>/market-guide/stock/XXXXX</code></li>
            <li>The number (XXXXX) is the stock ID</li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
};

export default StockConfiguration;
