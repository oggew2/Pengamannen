import { useState, useEffect } from 'react';
import { Box, Flex, Text, VStack, HStack, Button, Input } from '@chakra-ui/react';
import { api } from '../api/client';

interface Settings {
  displayCurrency: string;
  numberFormat: string;
  chartStyle: string;
  defaultStrategy: string;
  portfolioValue: number;
}

interface AuthState {
  authenticated: boolean;
  email?: string;
  name?: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>(() => {
    const saved = localStorage.getItem('appSettings');
    return saved ? JSON.parse(saved) : {
      displayCurrency: 'SEK', numberFormat: 'sv-SE', chartStyle: 'line',
      defaultStrategy: 'sammansatt_momentum', portfolioValue: 100000
    };
  });
  const [exportStatus, setExportStatus] = useState('');
  const [auth, setAuth] = useState<AuthState>({ authenticated: false });
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    try {
      const resp = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } });
      const data = await resp.json();
      if (data.authenticated) {
        setAuth({ authenticated: true, email: data.email, name: data.name });
      }
    } catch { /* ignore */ }
  };

  const handleLogin = async () => {
    setAuthError('');
    setAuthLoading(true);
    try {
      const resp = await fetch(`/api/auth/login?email=${encodeURIComponent(loginEmail)}&password=${encodeURIComponent(loginPassword)}`, { method: 'POST' });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Login failed');
      }
      const data = await resp.json();
      localStorage.setItem('authToken', data.token);
      setAuth({ authenticated: true, email: data.email, name: data.name });
      setLoginEmail('');
      setLoginPassword('');
    } catch (e: any) {
      setAuthError(e.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async () => {
    setAuthError('');
    setAuthLoading(true);
    try {
      const resp = await fetch(`/api/auth/register?email=${encodeURIComponent(loginEmail)}&password=${encodeURIComponent(loginPassword)}`, { method: 'POST' });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Registration failed');
      }
      await handleLogin();
    } catch (e: any) {
      setAuthError(e.message);
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    const token = localStorage.getItem('authToken');
    if (token) {
      await fetch(`/api/auth/logout?token=${token}`, { method: 'POST' }).catch(() => {});
    }
    localStorage.removeItem('authToken');
    setAuth({ authenticated: false });
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

  const clearCache = async () => {
    try {
      await fetch('/api/cache/clear', { method: 'POST' });
      setExportStatus('Cache cleared!');
    } catch { setExportStatus('Clear failed'); }
  };

  const SelectBox = ({ value, options, onChange }: { value: string; options: { value: string; label: string }[]; onChange: (v: string) => void }) => (
    <select value={value} onChange={(e) => onChange(e.target.value)} style={{ background: '#374151', color: '#f3f4f6', border: 'none', borderRadius: '6px', padding: '6px 12px', fontSize: '14px' }}>
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );

  return (
    <VStack gap="24px" align="stretch">
      <Text fontSize="2xl" fontWeight="bold" color="fg">Settings & Preferences</Text>

      {/* Account & Security */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Account & Security</Text>
        {auth.authenticated ? (
          <VStack align="stretch" gap="16px">
            <Flex justify="space-between" align="center">
              <VStack align="start" gap="0">
                <Text fontSize="sm" color="fg">Email</Text>
                <Text fontSize="xs" color="fg.muted">{auth.email}</Text>
              </VStack>
              <Button size="sm" variant="outline" borderColor="error.fg" color="error.fg" onClick={handleLogout}>Logout</Button>
            </Flex>
            {auth.name && (
              <Flex justify="space-between" align="center">
                <Text fontSize="sm" color="fg.muted">Logged in as {auth.name}</Text>
              </Flex>
            )}
          </VStack>
        ) : (
          <VStack align="stretch" gap="12px">
            <Input placeholder="Email" value={loginEmail} onChange={e => setLoginEmail(e.target.value)} size="sm" bg="bg.muted" borderColor="border" />
            <Input placeholder="Password" type="password" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} size="sm" bg="bg.muted" borderColor="border" />
            {authError && <Text fontSize="xs" color="error.fg">{authError}</Text>}
            <HStack gap="8px">
              <Button size="sm" bg="brand.solid" color="white" onClick={handleLogin} disabled={authLoading}>Login</Button>
              <Button size="sm" variant="outline" borderColor="brand.fg" color="brand.fg" onClick={handleRegister} disabled={authLoading}>Register</Button>
            </HStack>
          </VStack>
        )}
      </Box>

      {/* Display Preferences */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Display Preferences</Text>
        <VStack align="stretch" gap="16px">
          <Flex justify="space-between" align="center">
            <Text fontSize="sm" color="fg.muted">Currency</Text>
            <SelectBox value={settings.displayCurrency} options={[{ value: 'SEK', label: 'SEK' }, { value: 'EUR', label: 'EUR' }, { value: 'USD', label: 'USD' }]} onChange={v => saveSettings({ ...settings, displayCurrency: v })} />
          </Flex>
          <Flex justify="space-between" align="center">
            <Text fontSize="sm" color="fg.muted">Number Format</Text>
            <SelectBox value={settings.numberFormat} options={[{ value: 'sv-SE', label: '1 234,56' }, { value: 'en-US', label: '1,234.56' }]} onChange={v => saveSettings({ ...settings, numberFormat: v })} />
          </Flex>
          <Flex justify="space-between" align="center">
            <Text fontSize="sm" color="fg.muted">Chart Style</Text>
            <SelectBox value={settings.chartStyle} options={[{ value: 'line', label: 'Line' }, { value: 'area', label: 'Area' }]} onChange={v => saveSettings({ ...settings, chartStyle: v })} />
          </Flex>
        </VStack>
      </Box>

      {/* Portfolio Configuration */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Portfolio Configuration</Text>
        <VStack align="stretch" gap="16px">
          <Flex justify="space-between" align="center">
            <VStack align="start" gap="0">
              <Text fontSize="sm" color="fg.muted">Default Strategy</Text>
              <Text fontSize="xs" color="fg.subtle">Used for backtests and analysis</Text>
            </VStack>
            <SelectBox value={settings.defaultStrategy} options={[
              { value: 'sammansatt_momentum', label: 'Momentum' },
              { value: 'trendande_varde', label: 'Värde' },
              { value: 'trendande_utdelning', label: 'Utdelning' },
              { value: 'trendande_kvalitet', label: 'Kvalitet' }
            ]} onChange={v => saveSettings({ ...settings, defaultStrategy: v })} />
          </Flex>
          <Flex justify="space-between" align="center">
            <VStack align="start" gap="0">
              <Text fontSize="sm" color="fg.muted">Portfolio Value</Text>
              <Text fontSize="xs" color="fg.subtle">For rebalancing calculations</Text>
            </VStack>
            <HStack>
              <Input value={settings.portfolioValue} onChange={e => saveSettings({ ...settings, portfolioValue: Number(e.target.value) })} size="sm" bg="bg.muted" borderColor="border" w="120px" type="number" />
              <Text fontSize="sm" color="fg.subtle">kr</Text>
            </HStack>
          </Flex>
        </VStack>
      </Box>

      {/* Data Export */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Data Export</Text>
        <VStack align="stretch" gap="12px">
          <Flex justify="space-between" align="center">
            <VStack align="start" gap="0">
              <Text fontSize="sm" color="fg.muted">Export Portfolio</Text>
              <Text fontSize="xs" color="fg.subtle">Download holdings as CSV</Text>
            </VStack>
            <Button size="sm" variant="outline" borderColor="brand.fg" color="brand.fg" onClick={exportPortfolio}>Export CSV</Button>
          </Flex>
          <Flex justify="space-between" align="center">
            <VStack align="start" gap="0">
              <Text fontSize="sm" color="fg.muted">Clear Cache</Text>
              <Text fontSize="xs" color="fg.subtle">Force refresh all data</Text>
            </VStack>
            <Button size="sm" variant="outline" borderColor="error.fg" color="error.fg" onClick={clearCache}>Clear</Button>
          </Flex>
          {exportStatus && <Text fontSize="sm" color="success.fg">{exportStatus}</Text>}
        </VStack>
      </Box>

      {/* About */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="8px">About</Text>
        <Text fontSize="sm" color="fg.muted">Börslabbet Clone v1.0</Text>
        <Text fontSize="xs" color="fg.subtle" mt="4px">Swedish stock strategy platform implementing Börslabbet's proven investment strategies.</Text>
      </Box>
    </VStack>
  );
}
