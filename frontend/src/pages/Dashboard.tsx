import { VStack, SimpleGrid, Box, Text } from '@chakra-ui/react';
import { AlertsBanner } from '../components/AlertsBanner';
import { DataIntegrityBanner } from '../components/DataIntegrityBanner';
import { PortfolioTracker } from '../components/PortfolioTracker';
import { DailyStats } from '../components/DailyStats';
import { Achievements } from '../components/Achievements';
import { NotificationSettings } from '../components/NotificationSettings';
import { ThemeCustomization } from '../components/ThemeCustomization';
import { StaggerContainer, StaggerItem } from '../components/Animations';
import { useState } from 'react';

export function Dashboard() {
  const [showSettings, setShowSettings] = useState(false);
  
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
          <Achievements />
        </StaggerItem>
        
        {/* Settings toggle */}
        <StaggerItem>
          <Box 
            bg="bg" 
            borderRadius="8px" 
            p="12px" 
            borderWidth="1px" 
            borderColor="border"
            cursor="pointer"
            onClick={() => setShowSettings(!showSettings)}
            _hover={{ borderColor: 'blue.400' }}
            transition="all 0.15s"
          >
            <Text fontSize="sm" color="fg.muted" textAlign="center">
              {showSettings ? '▲ Dölj inställningar' : '⚙️ Visa inställningar'}
            </Text>
          </Box>
        </StaggerItem>
        
        {showSettings && (
          <StaggerItem>
            <SimpleGrid columns={{ base: 1, md: 2 }} gap="16px">
              <NotificationSettings />
              <ThemeCustomization />
            </SimpleGrid>
          </StaggerItem>
        )}
      </VStack>
    </StaggerContainer>
  );
}
