import { Box, VStack, HStack, Text, Switch } from '@chakra-ui/react';
import { useState, useEffect } from 'react';

interface NotificationSettings {
  rebalanceReminder: boolean;
  priceAlerts: boolean;
  rankingChanges: boolean;
  weeklyDigest: boolean;
  rebalanceFrequency: 'quarterly' | 'monthly';
}

const DEFAULT_SETTINGS: NotificationSettings = {
  rebalanceReminder: true,
  priceAlerts: false,
  rankingChanges: true,
  weeklyDigest: false,
  rebalanceFrequency: 'quarterly',
};

export function NotificationSettings() {
  const [settings, setSettings] = useState<NotificationSettings>(DEFAULT_SETTINGS);
  
  useEffect(() => {
    const saved = localStorage.getItem('notification_settings');
    if (saved) setSettings(JSON.parse(saved));
  }, []);
  
  const toggle = (key: keyof NotificationSettings) => {
    if (key === 'rebalanceFrequency') return;
    const updated = { ...settings, [key]: !settings[key] };
    setSettings(updated);
    localStorage.setItem('notification_settings', JSON.stringify(updated));
  };
  
  const setFrequency = (freq: 'quarterly' | 'monthly') => {
    const updated = { ...settings, rebalanceFrequency: freq };
    setSettings(updated);
    localStorage.setItem('notification_settings', JSON.stringify(updated));
  };

  const options = [
    { key: 'rebalanceReminder' as const, label: '🔔 Ombalanseringspåminnelse', desc: 'Påminn 3 dagar före' },
    { key: 'priceAlerts' as const, label: '📈 Prisvarningar', desc: 'Notis vid ±10% prisrörelse' },
    { key: 'rankingChanges' as const, label: '📊 Rankingändringar', desc: 'Notis när dina aktier byter rank' },
    { key: 'weeklyDigest' as const, label: '📧 Veckobrev', desc: 'Sammanfattning varje söndag' },
  ];

  return (
    <Box bg="bg" borderRadius="8px" p="16px" borderWidth="1px" borderColor="border">
      <Text fontSize="sm" fontWeight="semibold" mb="12px">🔔 Notifikationer</Text>
      <VStack gap="12px" align="stretch">
        {/* Rebalance frequency selector */}
        <Box p="8px" bg="bg.subtle" borderRadius="6px">
          <Text fontSize="sm" mb="8px">📅 Ombalanseringsfrekvens</Text>
          <HStack gap="8px">
            {(['quarterly', 'monthly'] as const).map(freq => (
              <Box
                key={freq}
                px="12px"
                py="6px"
                bg={settings.rebalanceFrequency === freq ? 'blue.600' : 'bg'}
                color={settings.rebalanceFrequency === freq ? 'white' : 'fg.muted'}
                borderRadius="6px"
                cursor="pointer"
                fontSize="sm"
                onClick={() => setFrequency(freq)}
                transition="all 0.15s"
              >
                {freq === 'quarterly' ? 'Kvartalsvis' : 'Månadsvis'}
              </Box>
            ))}
          </HStack>
          <Text fontSize="xs" color="fg.muted" mt="4px">
            {settings.rebalanceFrequency === 'quarterly' 
              ? 'Mars, juni, september, december (rekommenderat)' 
              : 'Varje månad (högre avgifter)'}
          </Text>
        </Box>
        
        {options.map(opt => (
          <HStack key={opt.key} justify="space-between" p="8px" bg="bg.subtle" borderRadius="6px">
            <Box>
              <Text fontSize="sm">{opt.label}</Text>
              <Text fontSize="xs" color="fg.muted">{opt.desc}</Text>
            </Box>
            <Switch.Root checked={settings[opt.key] as boolean} onCheckedChange={() => toggle(opt.key)}>
              <Switch.HiddenInput />
              <Switch.Control>
                <Switch.Thumb />
              </Switch.Control>
            </Switch.Root>
          </HStack>
        ))}
      </VStack>
      <Text fontSize="xs" color="fg.muted" mt="12px">
        💡 iOS: Lägg till appen på hemskärmen för push-notiser (Safari → Dela → Lägg till på hemskärmen)
      </Text>
    </Box>
  );
}

// Export for use in PortfolioTracker
export function getRebalanceFrequency(): 'quarterly' | 'monthly' {
  try {
    const saved = localStorage.getItem('notification_settings');
    if (saved) {
      const settings = JSON.parse(saved);
      return settings.rebalanceFrequency || 'quarterly';
    }
  } catch {}
  return 'quarterly';
}
