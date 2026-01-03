import { useState } from 'react';
import { Box, Flex, Text, VStack, HStack, Button, Input, Skeleton } from '@chakra-ui/react';
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
          <Text fontSize="2xl" fontWeight="bold" color="gray.50">Alerts & Notifications</Text>
          {unreadCount > 0 && (
            <Box bg="error.500" color="white" px="8px" py="2px" borderRadius="full" fontSize="xs">{unreadCount}</Box>
          )}
        </HStack>
        <Button size="sm" variant="ghost" color="gray.300" onClick={markAllRead}>Mark all read</Button>
      </Flex>

      {/* Notification Center */}
      <Box bg="gray.700" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">Recent Notifications</Text>
        {allAlerts.length === 0 ? (
          <Text fontSize="sm" color="gray.400">No notifications</Text>
        ) : (
          <VStack align="stretch" gap="12px">
            {allAlerts.slice(0, 10).map(alert => (
              <Flex key={alert.id} justify="space-between" align="center" p="12px" bg={alert.read ? 'gray.600' : 'gray.650'} borderRadius="6px" borderLeft="3px solid" borderLeftColor={alert.type === 'rebalance' ? 'brand.500' : alert.type === 'price' ? 'warning.500' : 'success.500'}>
                <VStack align="start" gap="2px">
                  <Text fontSize="sm" color="gray.100">{alert.message}</Text>
                  <Text fontSize="xs" color="gray.400">{alert.date}</Text>
                </VStack>
                <Button size="xs" variant="ghost" color="gray.400" onClick={() => dismissAlert(alert.id)}>✕</Button>
              </Flex>
            ))}
          </VStack>
        )}
      </Box>

      {/* Add Price Alert */}
      <Box bg="gray.700" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">Add Price Alert</Text>
        <HStack gap="12px">
          <Input placeholder="Ticker (e.g. ERIC-B)" value={newPriceAlert.ticker} onChange={e => setNewPriceAlert({ ...newPriceAlert, ticker: e.target.value })} size="sm" bg="gray.600" border="none" w="150px" />
          <Input placeholder="Target price" value={newPriceAlert.price} onChange={e => setNewPriceAlert({ ...newPriceAlert, price: e.target.value })} size="sm" bg="gray.600" border="none" w="120px" type="number" />
          <Button size="sm" bg="brand.500" color="white" onClick={addPriceAlert}>Add Alert</Button>
        </HStack>
      </Box>

      {/* Alert Settings */}
      <Box bg="gray.700" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">Alert Settings</Text>
        <VStack align="stretch" gap="12px">
          {[
            { key: 'priceAlerts', label: 'Price Alerts', desc: 'Get notified when stocks hit target prices' },
            { key: 'dividendAlerts', label: 'Dividend Alerts', desc: 'Upcoming dividend payments' },
            { key: 'rebalanceReminders', label: 'Rebalance Reminders', desc: 'Reminders before rebalancing dates' },
            { key: 'strategyChanges', label: 'Strategy Changes', desc: 'When stocks enter/exit strategies' },
          ].map(({ key, label, desc }) => (
            <Flex key={key} justify="space-between" align="center">
              <VStack align="start" gap="0">
                <Text fontSize="sm" color="gray.100">{label}</Text>
                <Text fontSize="xs" color="gray.400">{desc}</Text>
              </VStack>
              <Box as="button" role="switch" aria-checked={settings[key as keyof AlertSettings] ? 'true' : 'false'} aria-label={label} w="44px" h="24px" borderRadius="12px" bg={settings[key as keyof AlertSettings] ? 'brand.500' : 'gray.500'} position="relative" onClick={() => toggleSetting(key as keyof AlertSettings)} transition="background 200ms">
                <Box position="absolute" top="2px" left={settings[key as keyof AlertSettings] ? '22px' : '2px'} w="20px" h="20px" borderRadius="full" bg="white" transition="left 200ms" boxShadow="sm" />
              </Box>
            </Flex>
          ))}
        </VStack>

        <Box mt="24px" pt="16px" borderTop="1px solid" borderColor="gray.600">
          <Flex justify="space-between" align="center" mb="12px">
            <VStack align="start" gap="0">
              <Text fontSize="sm" color="gray.100">Email Notifications</Text>
              <Text fontSize="xs" color="gray.400">Receive alerts via email</Text>
            </VStack>
            <Box as="button" role="switch" aria-checked={settings.emailNotifications ? 'true' : 'false'} aria-label="Email Notifications" w="44px" h="24px" borderRadius="12px" bg={settings.emailNotifications ? 'brand.500' : 'gray.500'} position="relative" onClick={() => toggleSetting('emailNotifications')} transition="background 200ms">
              <Box position="absolute" top="2px" left={settings.emailNotifications ? '22px' : '2px'} w="20px" h="20px" borderRadius="full" bg="white" transition="left 200ms" boxShadow="sm" />
            </Box>
          </Flex>
          {settings.emailNotifications && (
            <Input placeholder="your@email.com" value={settings.email} onChange={e => saveSettings({ ...settings, email: e.target.value })} size="sm" bg="gray.600" border="none" />
          )}
        </Box>
      </Box>
    </VStack>
  );
}
