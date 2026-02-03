import { Component, ErrorInfo, ReactNode } from 'react';
import { Box, Heading, Text, Button, VStack } from '@chakra-ui/react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

async function clearAllCaches() {
  // Clear service worker caches
  if ('caches' in window) {
    const keys = await caches.keys();
    await Promise.all(keys.map(k => caches.delete(k)));
  }
  // Unregister service workers
  if ('serviceWorker' in navigator) {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map(r => r.unregister()));
  }
  // Clear localStorage
  localStorage.clear();
  sessionStorage.clear();
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  handleHardReset = async () => {
    await clearAllCaches();
    window.location.href = '/?cache_bust=' + Date.now();
  };

  render() {
    if (this.state.hasError) {
      return (
        <Box p={8} textAlign="center">
          <VStack gap={4}>
            <Heading size="lg">Något gick fel</Heading>
            <Text color="gray.600">
              Ett oväntat fel uppstod.
            </Text>
            {this.state.error && (
              <Text fontSize="xs" color="red.400" fontFamily="mono" maxW="400px" overflow="auto">
                {this.state.error.message}
              </Text>
            )}
            <Button onClick={() => window.location.reload()} colorPalette="blue">
              Ladda om
            </Button>
            <Button onClick={this.handleHardReset} variant="outline" size="sm">
              Rensa cache och ladda om
            </Button>
          </VStack>
        </Box>
      );
    }

    return this.props.children;
  }
}
