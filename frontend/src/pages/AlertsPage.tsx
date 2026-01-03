import { useState } from 'react';
import { Box, Flex, Text, VStack, HStack, Button, Input, Skeleton, Switch } from '@chakra-ui/react';
import { useRebalanceDates } from '../api/hooks';

interface Alert {
  id: string;
  type: 'price' | 'dividend' | 'rebalance' | 'strategy';
  ticker?: string;
  message: string;
  date: string;
  read: boolean;
}

interface AlertSettings {
  priceAlerts: boolean;
  dividendAlerts: boolean;
  rebalanceReminders: boolean;
  strategyChanges: boolean;
  emailNotifications: boolean;
  email: string;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [settings, setSettings] = useState<AlertSettings>(() => {
    const saved = localStorage.getItem('alertSettings');
    return saved ? JSON.parse(saved) : {
      priceAlerts: true, dividendAlerts: true, rebalanceReminders: true,
      strategyChanges: true, emailNotifications: false, email: ''
    };
  });
  const [newPriceAlert, setNewPriceAlert] = useState({ ticker: '', price: '' });

  const { data: rebalanceDates = [], isLoading, isError } = useRebalanceDates();

  // Build alerts from rebalance dates + localStorage
  const allAlerts = [
    ...rebalanceDates.map(d => ({
      id: `rebal-${d.strategy_name}`,
      type: 'rebalance' as const,
      message: `${d.strategy_name} rebalancing on ${d.next_date}`,
      date: d.next_date,
      read: false
    })),
    ...JSON.parse(localStorage.getItem('userAlerts') || '[]'),
    ...alerts.filter(a => a.type === 'price'),
  ];

  const saveSettings = (newSettings: AlertSettings) => {
    setSettings(newSettings);
    localStorage.setItem('alertSettings', JSON.stringify(newSettings));
  };

  const toggleSetting = (key: keyof AlertSettings) => {
    if (key === 'email') return;
    saveSettings({ ...settings, [key]: !settings[key] });
  };

  const addPriceAlert = () => {
    if (!newPriceAlert.ticker || !newPriceAlert.price) return;
    const alert: Alert = {
      id: `price-${Date.now()}`,
      type: 'price',
      ticker: newPriceAlert.ticker.toUpperCase(),
      message: `Price alert: ${newPriceAlert.ticker.toUpperCase()} at ${newPriceAlert.price} kr`,
      date: new Date().toISOString().split('T')[0],
      read: false
    };
    const updated = [...alerts, alert];
    setAlerts(updated);
    localStorage.setItem('userAlerts', JSON.stringify(updated.filter(a => a.type === 'price')));
    setNewPriceAlert({ ticker: '', price: '' });
  };

  const dismissAlert = (id: string) => {
    const updated = allAlerts.filter(a => a.id !== id);
    setAlerts(updated.filter(a => a.type === 'price'));
    localStorage.setItem('userAlerts', JSON.stringify(updated.filter(a => a.type === 'price')));
  };

  const markAllRead = () => {
    // For now, just clear local state
  };

  if (isError) {
    return (
      <VStack gap="24px" align="stretch">
        <Box bg="red.900/20" borderColor="red.500" borderWidth="1px" borderRadius="8px" p="16px">
          <Text color="red.400" fontWeight="semibold">Failed to load alerts</Text>
        </Box>
      </VStack>
    );
  }

  if (isLoading) {
    return <VStack gap="24px" align="stretch"><Skeleton height="400px" borderRadius="8px" /></VStack>;
  }

  const unreadCount = allAlerts.filter(a => !a.read).length;

  return (
    <VStack gap="24px" align="stretch">
      <Flex justify="space-between" align="center">
        <HStack gap="12px">
          <Text fontSize="2xl" fontWeight="bold" color="fg">Alerts & Notifications</Text>
          {unreadCount > 0 && (
            <Box bg="error.500" color="white" px="8px" py="2px" borderRadius="full" fontSize="xs">{unreadCount}</Box>
          )}
        </HStack>
        <Button size="sm" variant="ghost" color="fg.muted" onClick={markAllRead}>Mark all read</Button>
      </Flex>

      {/* Notification Center */}
      <Box bg="bg.subtle" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Recent Notifications</Text>
        {allAlerts.length === 0 ? (
          <Text fontSize="sm" color="fg.subtle">No notifications</Text>
        ) : (
          <VStack align="stretch" gap="12px">
            {allAlerts.slice(0, 10).map(alert => (
              <Flex key={alert.id} justify="space-between" align="center" p="12px" bg={alert.read ? 'border' : 'bg.hover'} borderRadius="6px" borderLeft="3px solid" borderLeftColor={alert.type === 'rebalance' ? 'brand.500' : alert.type === 'price' ? 'warning.500' : 'success.500'}>
                <VStack align="start" gap="2px">
                  <Text fontSize="sm" color="fg">{alert.message}</Text>
                  <Text fontSize="xs" color="fg.subtle">{alert.date}</Text>
                </VStack>
                <Button size="xs" variant="ghost" color="fg.subtle" onClick={() => dismissAlert(alert.id)}>✕</Button>
              </Flex>
            ))}
          </VStack>
        )}
      </Box>

      {/* Add Price Alert */}
      <Box bg="bg.subtle" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Add Price Alert</Text>
        <HStack gap="12px">
          <Input placeholder="Ticker (e.g. ERIC-B)" value={newPriceAlert.ticker} onChange={e => setNewPriceAlert({ ...newPriceAlert, ticker: e.target.value })} size="sm" bg="border" border="none" w="150px" />
          <Input placeholder="Target price" value={newPriceAlert.price} onChange={e => setNewPriceAlert({ ...newPriceAlert, price: e.target.value })} size="sm" bg="border" border="none" w="120px" type="number" />
          <Button size="sm" bg="brand.500" color="white" onClick={addPriceAlert}>Add Alert</Button>
        </HStack>
      </Box>

      {/* Alert Settings */}
      <Box bg="bg.subtle" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Alert Settings</Text>
        <VStack align="stretch" gap="12px">
          {[
            { key: 'priceAlerts', label: 'Price Alerts', desc: 'Get notified when stocks hit target prices' },
            { key: 'dividendAlerts', label: 'Dividend Alerts', desc: 'Upcoming dividend payments' },
            { key: 'rebalanceReminders', label: 'Rebalance Reminders', desc: 'Reminders before rebalancing dates' },
            { key: 'strategyChanges', label: 'Strategy Changes', desc: 'When stocks enter/exit strategies' },
          ].map(({ key, label, desc }) => (
            <Flex key={key} justify="space-between" align="center">
              <VStack align="start" gap="0">
                <Text fontSize="sm" color="fg">{label}</Text>
                <Text fontSize="xs" color="fg.subtle">{desc}</Text>
              </VStack>
              <Switch.Root checked={!!settings[key as keyof AlertSettings]} onCheckedChange={() => toggleSetting(key as keyof AlertSettings)} colorPalette="blue">
                <Switch.HiddenInput />
                <Switch.Control />
              </Switch.Root>
            </Flex>
          ))}
        </VStack>

        <Box mt="24px" pt="16px" borderTop="1px solid" borderColor="border">
          <Flex justify="space-between" align="center" mb="12px">
            <VStack align="start" gap="0">
              <Text fontSize="sm" color="fg">Email Notifications</Text>
              <Text fontSize="xs" color="fg.subtle">Receive alerts via email</Text>
            </VStack>
            <Switch.Root checked={settings.emailNotifications} onCheckedChange={() => toggleSetting('emailNotifications')} colorPalette="blue">
              <Switch.HiddenInput />
              <Switch.Control />
            </Switch.Root>
          </Flex>
          {settings.emailNotifications && (
            <Input placeholder="your@email.com" value={settings.email} onChange={e => saveSettings({ ...settings, email: e.target.value })} size="sm" bg="border" border="none" />
          )}
        </Box>
      </Box>
    </VStack>
  );
}
