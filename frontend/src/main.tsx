import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ChakraProvider } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider, QueryCache } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { App } from './App';
import { system } from './theme';
import './index.css';

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // Log errors for debugging (could integrate with error tracking service)
      console.error(`Query error [${query.queryKey}]:`, error);
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,      // 5 min - data considered fresh
      gcTime: 30 * 60 * 1000,        // 30 min - keep in cache
      refetchOnWindowFocus: false,   // Don't refetch on tab focus (quarterly rebalancing app)
      retry: 1,                       // Retry failed requests once
    },
  },
});

// Export for logout/multi-user cache clearing
export { queryClient };

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ChakraProvider value={system}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ChakraProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </React.StrictMode>
);

// Hide the loading screen now that React has mounted
if (typeof window !== 'undefined' && (window as any).hideAppLoader) {
  (window as any).hideAppLoader();
}
