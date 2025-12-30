import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Settings, Clock, RefreshCw, Save, AlertCircle } from 'lucide-react';

interface SyncConfig {
  auto_sync_enabled: boolean;
  sync_interval_hours: number;
  sync_on_visit: boolean;
  visit_threshold_minutes: number;
  cache_ttl_minutes: number;
  max_concurrent_requests: number;
  request_delay_seconds: number;
  retry_failed_after_minutes: number;
  last_sync: string | null;
  last_visit: string | null;
}

interface SyncConfigResponse {
  config: SyncConfig;
  next_sync: string;
  should_sync_now: boolean;
  should_sync_on_visit: boolean;
}

const SyncConfiguration: React.FC = () => {
  const [config, setConfig] = useState<SyncConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [localConfig, setLocalConfig] = useState<SyncConfig | null>(null);

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/data/sync-config');
      const data = await response.json();
      setConfig(data);
      setLocalConfig(data.config);
    } catch (error) {
      console.error('Failed to fetch sync config:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    if (!localConfig) return;
    
    setSaving(true);
    try {
      const response = await fetch('/api/data/sync-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(localConfig)
      });
      
      if (response.ok) {
        await fetchConfig(); // Refresh config
        alert('Configuration saved successfully!');
      } else {
        alert('Failed to save configuration');
      }
    } catch (error) {
      alert(`Error saving configuration: ${error}`);
    } finally {
      setSaving(false);
    }
  };

  const triggerFullSync = async () => {
    setSyncing(true);
    try {
      const response = await fetch('/api/data/sync-full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method: 'avanza', force: true })
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(`Full sync completed! ${result.sync_result?.successful || 0} stocks updated`);
        await fetchConfig(); // Refresh to show new last_sync time
      } else {
        alert('Full sync failed');
      }
    } catch (error) {
      alert(`Error during full sync: ${error}`);
    } finally {
      setSyncing(false);
    }
  };

  const updateLocalConfig = (key: keyof SyncConfig, value: any) => {
    if (!localConfig) return;
    setLocalConfig({ ...localConfig, [key]: value });
  };

  const formatLastTime = (timestamp: string | null) => {
    if (!timestamp) return 'Never';
    return new Date(timestamp).toLocaleString();
  };

  useEffect(() => {
    fetchConfig();
    // Refresh every 30 seconds
    const interval = setInterval(fetchConfig, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div className="p-8">Loading sync configuration...</div>;
  }

  if (!config || !localConfig) {
    return <div className="p-8">Failed to load sync configuration</div>;
  }

  const hasChanges = JSON.stringify(config.config) !== JSON.stringify(localConfig);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Sync Configuration</h1>
        <div className="flex items-center space-x-2">
          {config.should_sync_now && (
            <Badge variant="destructive">
              <AlertCircle className="w-3 h-3 mr-1" />
              Sync Overdue
            </Badge>
          )}
          <Button onClick={fetchConfig} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Current Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Clock className="w-5 h-5 mr-2" />
            Current Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="text-sm text-gray-600">Last Sync</div>
              <div className="font-medium">{formatLastTime(config.config.last_sync)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Next Sync</div>
              <div className="font-medium">{config.next_sync}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Last Visit</div>
              <div className="font-medium">{formatLastTime(config.config.last_visit)}</div>
            </div>
          </div>
          
          <div className="mt-4">
            <Button 
              onClick={triggerFullSync} 
              disabled={syncing}
              className="w-full md:w-auto"
            >
              {syncing ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              {syncing ? 'Syncing...' : 'Full Manual Sync'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Configuration Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Settings className="w-5 h-5 mr-2" />
            Sync Settings
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Auto Sync */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Auto Sync Enabled</div>
              <div className="text-sm text-gray-600">Automatically sync data at intervals</div>
            </div>
            <Switch
              checked={localConfig.auto_sync_enabled}
              onCheckedChange={(checked) => updateLocalConfig('auto_sync_enabled', checked)}
            />
          </div>

          {/* Sync Interval */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Sync Interval (hours)
            </label>
            <Input
              type="number"
              min="1"
              max="168"
              value={localConfig.sync_interval_hours}
              onChange={(e) => updateLocalConfig('sync_interval_hours', parseInt(e.target.value))}
              className="w-32"
            />
            <div className="text-sm text-gray-600 mt-1">
              How often to automatically sync data (1-168 hours)
            </div>
          </div>

          {/* Sync on Visit */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Sync on Visit</div>
              <div className="text-sm text-gray-600">Sync when users visit after threshold</div>
            </div>
            <Switch
              checked={localConfig.sync_on_visit}
              onCheckedChange={(checked) => updateLocalConfig('sync_on_visit', checked)}
            />
          </div>

          {/* Visit Threshold */}
          {localConfig.sync_on_visit && (
            <div>
              <label className="block text-sm font-medium mb-2">
                Visit Threshold (minutes)
              </label>
              <Input
                type="number"
                min="5"
                max="1440"
                value={localConfig.visit_threshold_minutes}
                onChange={(e) => updateLocalConfig('visit_threshold_minutes', parseInt(e.target.value))}
                className="w-32"
              />
              <div className="text-sm text-gray-600 mt-1">
                Only sync if last visit was more than this many minutes ago
              </div>
            </div>
          )}

          {/* Cache TTL */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Cache TTL (minutes)
            </label>
            <Input
              type="number"
              min="5"
              max="1440"
              value={localConfig.cache_ttl_minutes}
              onChange={(e) => updateLocalConfig('cache_ttl_minutes', parseInt(e.target.value))}
              className="w-32"
            />
            <div className="text-sm text-gray-600 mt-1">
              How long to cache stock data before refetching
            </div>
          </div>

          {/* Performance Settings */}
          <div className="border-t pt-4">
            <h3 className="font-medium mb-4">Performance Settings</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Max Concurrent Requests
                </label>
                <Input
                  type="number"
                  min="1"
                  max="10"
                  value={localConfig.max_concurrent_requests}
                  onChange={(e) => updateLocalConfig('max_concurrent_requests', parseInt(e.target.value))}
                  className="w-24"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">
                  Request Delay (seconds)
                </label>
                <Input
                  type="number"
                  min="0.5"
                  max="10"
                  step="0.5"
                  value={localConfig.request_delay_seconds}
                  onChange={(e) => updateLocalConfig('request_delay_seconds', parseFloat(e.target.value))}
                  className="w-24"
                />
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end space-x-2 pt-4 border-t">
            <Button
              onClick={saveConfig}
              disabled={!hasChanges || saving}
              variant={hasChanges ? "default" : "secondary"}
            >
              {saving ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              {saving ? 'Saving...' : hasChanges ? 'Save Changes' : 'No Changes'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SyncConfiguration;
