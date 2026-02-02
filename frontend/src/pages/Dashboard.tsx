import { VStack } from '@chakra-ui/react';
import { AlertsBanner } from '../components/AlertsBanner';
import { DataIntegrityBanner } from '../components/DataIntegrityBanner';
import { PortfolioTracker } from '../components/PortfolioTracker';

export function Dashboard() {
  return (
    <VStack gap="24px" align="stretch">
      <DataIntegrityBanner />
      <AlertsBanner />
      <PortfolioTracker />
    </VStack>
  );
}
