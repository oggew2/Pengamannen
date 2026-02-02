import { VStack } from '@chakra-ui/react';
import { AlertsBanner } from '../components/AlertsBanner';
import { DataIntegrityBanner } from '../components/DataIntegrityBanner';
import { PortfolioTracker } from '../components/PortfolioTracker';
import { StaggerContainer, StaggerItem } from '../components/Animations';

export function Dashboard() {
  return (
    <StaggerContainer>
      <VStack gap="24px" align="stretch">
        <StaggerItem>
          <DataIntegrityBanner />
        </StaggerItem>
        <StaggerItem>
          <AlertsBanner />
        </StaggerItem>
        <StaggerItem>
          <PortfolioTracker />
        </StaggerItem>
      </VStack>
    </StaggerContainer>
  );
}
