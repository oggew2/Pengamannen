import { useState, useEffect } from 'react';
import { Box, Flex, Text, VStack, HStack, Button, Grid } from '@chakra-ui/react';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

interface Settings {
  displayCurrency: string;
  numberFormat: string;
  chartStyle: string;
  defaultStrategy: string;
  portfolioValue: number;
}

interface UserInfo {
  id: number;
  email: string;
  name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [settings, setSettings] = useState<Settings>(() => {
    const saved = localStorage.getItem('appSettings');
    return saved ? JSON.parse(saved) : {
      displayCurrency: 'SEK', numberFormat: 'sv-SE', chartStyle: 'line',
      defaultStrategy: 'sammansatt_momentum', portfolioValue: 100000
    };
  });
  const [exportStatus, setExportStatus] = useState('');
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);

  useEffect(() => {
    if (user?.is_admin) {
      loadUsers();
    }
  }, [user]);

  const loadUsers = async () => {
    setUsersLoading(true);
    try {
      const resp = await fetch('/v1/admin/users', { credentials: 'include' });
      if (resp.ok) {
        const data = await resp.json();
        setUsers(data.users);
      }
    } catch { /* ignore */ }
    setUsersLoading(false);
  };

  const saveSettings = (newSettings: Settings) => {
    setSettings(newSettings);
    localStorage.setItem('appSettings', JSON.stringify(newSettings));
  };

  const exportPortfolio = async () => {
    try {
      const portfolio = await api.getPortfolio();
      const csv = ['Ticker,Name,Strategy,Weight', ...portfolio.holdings.map(h => `${h.ticker},${h.name || ''},${h.strategy},${h.weight}`)].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'portfolio.csv'; a.click();
      setExportStatus('Portfolio exported!');
      setTimeout(() => setExportStatus(''), 3000);
    } catch { setExportStatus('Export failed'); }
  };

  const SelectBox = ({ value, options, onChange }: { value: string; options: { value: string; label: string }[]; onChange: (v: string) => void }) => (
    <select value={value} onChange={(e) => onChange(e.target.value)} style={{ background: '#374151', color: '#f3f4f6', border: 'none', borderRadius: '6px', padding: '6px 12px', fontSize: '14px' }}>
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );

  return (
    <VStack gap="24px" align="stretch">
      <Text fontSize="2xl" fontWeight="bold" color="fg">Settings & Preferences</Text>

      {/* Account */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Account</Text>
        <VStack align="stretch" gap="16px">
          <Flex justify="space-between" align="center">
            <VStack align="start" gap="0">
              <Text fontSize="sm" color="fg">{user?.name}</Text>
              <Text fontSize="xs" color="fg.muted">{user?.email}</Text>
            </VStack>
            <Button size="sm" variant="outline" borderColor="error.fg" color="error.fg" onClick={logout}>Logout</Button>
          </Flex>
          <Flex justify="space-between" align="center">
            <VStack align="start" gap="0">
              <Text fontSize="sm" color="fg">Your Invite Code</Text>
              <Text fontSize="xs" color="fg.muted">Share this to let others register</Text>
            </VStack>
            <Text fontSize="sm" color="brand.fg" fontFamily="mono" fontWeight="bold">{user?.invite_code}</Text>
          </Flex>
        </VStack>
      </Box>

      {/* Admin Panel - only for admins */}
      {user?.is_admin && (
        <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
          <Flex justify="space-between" align="center" mb="16px">
            <Text fontSize="lg" fontWeight="semibold" color="fg">👑 Admin Panel</Text>
            <Text fontSize="sm" color="fg.muted">{users.length} registered users</Text>
          </Flex>
          {usersLoading ? (
            <Text color="fg.muted">Loading users...</Text>
          ) : (
            <VStack align="stretch" gap="8px">
              {users.map(u => (
                <Flex key={u.id} justify="space-between" align="center" p="12px" bg="bg.muted" borderRadius="md">
                  <VStack align="start" gap="0">
                    <HStack gap="8px">
                      <Text fontSize="sm" color="fg">{u.name}</Text>
                      {u.is_admin && <Text fontSize="xs" color="brand.fg">Admin</Text>}
                      {!u.is_active && <Text fontSize="xs" color="error.fg">Disabled</Text>}
                    </HStack>
                    <Text fontSize="xs" color="fg.muted">{u.email}</Text>
                  </VStack>
                  <Text fontSize="xs" color="fg.subtle">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('sv-SE') : 'N/A'}
                  </Text>
                </Flex>
              ))}
            </VStack>
          )}
        </Box>
      )}

      {/* Display Preferences */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Display Preferences</Text>
        <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)' }} gap="16px">
          <Flex justify="space-between" align="center">
            <Text fontSize="sm" color="fg.muted">Currency</Text>
            <SelectBox value={settings.displayCurrency} options={[{ value: 'SEK', label: 'SEK' }, { value: 'USD', label: 'USD' }, { value: 'EUR', label: 'EUR' }]} onChange={(v) => saveSettings({ ...settings, displayCurrency: v })} />
          </Flex>
          <Flex justify="space-between" align="center">
            <Text fontSize="sm" color="fg.muted">Number Format</Text>
            <SelectBox value={settings.numberFormat} options={[{ value: 'sv-SE', label: 'Swedish (1 234,56)' }, { value: 'en-US', label: 'US (1,234.56)' }]} onChange={(v) => saveSettings({ ...settings, numberFormat: v })} />
          </Flex>
          <Flex justify="space-between" align="center">
            <Text fontSize="sm" color="fg.muted">Default Strategy</Text>
            <SelectBox value={settings.defaultStrategy} options={[{ value: 'sammansatt_momentum', label: 'Momentum' }, { value: 'trendande_varde', label: 'Värde' }, { value: 'trendande_utdelning', label: 'Utdelning' }, { value: 'trendande_kvalitet', label: 'Kvalitet' }]} onChange={(v) => saveSettings({ ...settings, defaultStrategy: v })} />
          </Flex>
        </Grid>
      </Box>

      {/* Data & Export */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Data & Export</Text>
        <VStack align="stretch" gap="12px">
          <Flex justify="space-between" align="center">
            <VStack align="start" gap="0">
              <Text fontSize="sm" color="fg">Export Portfolio</Text>
              <Text fontSize="xs" color="fg.muted">Download as CSV</Text>
            </VStack>
            <Button size="sm" variant="outline" borderColor="border" color="fg" onClick={exportPortfolio}>Export</Button>
          </Flex>
          {exportStatus && <Text fontSize="sm" color="success.fg">{exportStatus}</Text>}
        </VStack>
      </Box>
    </VStack>
  );
}
