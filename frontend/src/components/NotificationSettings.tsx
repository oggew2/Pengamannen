import { Box, VStack, HStack, Text, Switch } from '@chakra-ui/react';
import { useState, useEffect } from 'react';

interface NotificationSettings {
  rebalanceReminder: boolean;
  priceAlerts: boolean;
  rankingChanges: boolean;
  weeklyDigest: boolean;
}

const DEFAULT_SETTINGS: NotificationSettings = {
  rebalanceReminder: true,
  priceAlerts: false,
  rankingChanges: true,
  weeklyDigest: false,
};

export function NotificationSettings() {
  const [settings, setSettings] = useState<NotificationSettings>(DEFAULT_SETTINGS);
  
  useEffect(() => {
    const saved = localStorage.getItem('notification_settings');
    if (saved) setSettings(JSON.parse(saved));
  }, []);
  
  const toggle = (key: keyof NotificationSettings) => {
    const updated = { ...settings, [key]: !settings[key] };
    setSettings(updated);
    localStorage.setItem('notification_settings', JSON.stringify(updated));
  };

  const options = [
    { key: 'rebalanceReminder' as const, label: '🔔 Ombalanseringspåminnelse', desc: 'Påminn 3 dagar före kvartalsslut' },
    { key: 'priceAlerts' as const, label: '📈 Prisvarningar', desc: 'Notis vid ±10% prisrörelse' },
    { key: 'rankingChanges' as const, label: '📊 Rankingändringar', desc: 'Notis när dina aktier byter rank' },
    { key: 'weeklyDigest' as const, label: '📧 Veckobrev', desc: 'Sammanfattning varje söndag' },
  ];

  return (
    <Box bg="bg" borderRadius="8px" p="16px" borderWidth="1px" borderColor="border">
      <Text fontSize="sm" fontWeight="semibold" mb="12px">🔔 Notifikationer</Text>
      <VStack gap="12px" align="stretch">
        {options.map(opt => (
          <HStack key={opt.key} justify="space-between" p="8px" bg="bg.subtle" borderRadius="6px">
            <Box>
              <Text fontSize="sm">{opt.label}</Text>
              <Text fontSize="xs" color="fg.muted">{opt.desc}</Text>
            </Box>
            <Switch.Root checked={settings[opt.key]} onCheckedChange={() => toggle(opt.key)}>
              <Switch.HiddenInput />
              <Switch.Control>
                <Switch.Thumb />
              </Switch.Control>
            </Switch.Root>
          </HStack>
        ))}
      </VStack>
      <Text fontSize="xs" color="fg.muted" mt="12px">
        💡 Notifikationer kräver webbläsartillstånd. Klicka på 🔔 i adressfältet för att aktivera.
      </Text>
    </Box>
  );
}
