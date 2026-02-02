import { VStack, Box, Text, HStack } from '@chakra-ui/react';
import { AlertsBanner } from '../components/AlertsBanner';
import { DataIntegrityBanner } from '../components/DataIntegrityBanner';
import { PortfolioTracker } from '../components/PortfolioTracker';
import { DailyStats } from '../components/DailyStats';
import { PushNotificationToggle } from '../components/PushNotificationToggle';
import { StaggerContainer, StaggerItem } from '../components/Animations';
import { useState, useEffect } from 'react';

function RebalanceFrequencyToggle() {
  const [freq, setFreq] = useState<'quarterly' | 'monthly'>('quarterly');
  
  useEffect(() => {
    try {
      const saved = localStorage.getItem('notification_settings');
      if (saved) {
        const s = JSON.parse(saved);
        if (s.rebalanceFrequency) setFreq(s.rebalanceFrequency);
      }
    } catch {}
  }, []);
  
  const toggle = (f: 'quarterly' | 'monthly') => {
    setFreq(f);
    try {
      const saved = localStorage.getItem('notification_settings');
      const settings = saved ? JSON.parse(saved) : {};
      settings.rebalanceFrequency = f;
      localStorage.setItem('notification_settings', JSON.stringify(settings));
      window.location.reload();
    } catch {}
  };

  return (
    <Box bg="bg" borderRadius="8px" p="12px" borderWidth="1px" borderColor="border">
      <HStack justify="space-between">
        <Text fontSize="sm" color="fg.muted">📅 Ombalanseringsfrekvens</Text>
        <HStack gap="4px">
          {(['quarterly', 'monthly'] as const).map(f => (
            <Box
              key={f}
              px="10px"
              py="4px"
              bg={freq === f ? 'blue.600' : 'bg.subtle'}
              color={freq === f ? 'white' : 'fg.muted'}
              borderRadius="6px"
              cursor="pointer"
              fontSize="xs"
              onClick={() => toggle(f)}
            >
              {f === 'quarterly' ? 'Kvartal' : 'Månad'}
            </Box>
          ))}
        </HStack>
      </HStack>
    </Box>
  );
}

export function Dashboard() {
  return (
    <StaggerContainer>
      <VStack gap="24px" align="stretch">
        <StaggerItem>
          <DailyStats />
        </StaggerItem>
        <StaggerItem>
          <DataIntegrityBanner />
        </StaggerItem>
        <StaggerItem>
          <AlertsBanner />
        </StaggerItem>
        <StaggerItem>
          <PortfolioTracker />
        </StaggerItem>
        <StaggerItem>
          <Box bg="bg" borderRadius="8px" p="12px" borderWidth="1px" borderColor="border">
            <VStack gap="8px" align="stretch">
              <Text fontSize="sm" fontWeight="semibold" color="fg.muted">⚙️ Inställningar</Text>
              <RebalanceFrequencyToggle />
              <PushNotificationToggle />
            </VStack>
          </Box>
        </StaggerItem>
      </VStack>
    </StaggerContainer>
  );
}
