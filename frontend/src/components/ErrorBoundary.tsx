import { Component, ErrorInfo, ReactNode } from 'react';
import { Box, Heading, Text, Button, VStack } from '@chakra-ui/react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
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

  render() {
    if (this.state.hasError) {
      return (
        <Box p={8} textAlign="center">
          <VStack gap={4}>
            <Heading size="lg">Något gick fel</Heading>
            <Text color="gray.600">
              Ett oväntat fel uppstod. Försök ladda om sidan.
            </Text>
            <Button onClick={() => window.location.reload()} colorScheme="blue">
              Ladda om
            </Button>
          </VStack>
        </Box>
      );
    }

    return this.props.children;
  }
}
