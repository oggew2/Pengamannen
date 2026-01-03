import { Routes, Route, Navigate } from 'react-router-dom';
import { Box, Flex, Text } from '@chakra-ui/react';
import { Suspense, lazy } from 'react';
import { Navigation } from './components/Navigation';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Dashboard } from './pages/Dashboard';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { Toaster } from './components/toaster';

// Lazy load pages
const StrategyPage = lazy(() => import('./pages/StrategyPage').then(m => ({ default: m.StrategyPage })));
const HistoricalBacktestPage = lazy(() => import('./pages/HistoricalBacktestPage').then(m => ({ default: m.HistoricalBacktestPage })));
const StockDetailPage = lazy(() => import('./pages/StockDetailPage'));
const DividendCalendarPage = lazy(() => import('./pages/DividendCalendarPage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const EducationPage = lazy(() => import('./pages/EducationPage'));
const GettingStartedPage = lazy(() => import('./pages/GettingStartedPage'));
const MinStrategiPage = lazy(() => import('./pages/MinStrategiPage'));
const DataManagementPage = lazy(() => import('./pages/DataManagementPage'));

const PageLoader = () => (
  <Box display="flex" justifyContent="center" alignItems="center" minH="200px">
    <Box className="skeleton" w="100%" maxW="600px" h="300px" borderRadius="lg" />
  </Box>
);

const AuthLoader = () => (
  <Flex minH="100vh" align="center" justify="center" bg="bg">
    <Text color="fg.muted">Loading...</Text>
  </Flex>
);

function ProtectedApp() {
  const { user, loading } = useAuth();

  if (loading) return <AuthLoader />;
  if (!user) return <LoginPage />;

  return (
    <>
      <Navigation />
      <Box
        as="main"
        ml={{ base: 0, lg: '240px' }}
        pb={{ base: '80px', md: 0 }}
        minH="100vh"
      >
        <Box maxW="1000px" mx="auto" px="24px" py="32px">
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/strategies/:type" element={<StrategyPage />} />
              <Route path="/rebalancing" element={<MinStrategiPage />} />
              <Route path="/backtesting/historical" element={<HistoricalBacktestPage />} />
              <Route path="/dividends" element={<DividendCalendarPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/data" element={<DataManagementPage />} />
              <Route path="/learn" element={<EducationPage />} />
              <Route path="/getting-started" element={<GettingStartedPage />} />
              <Route path="/stock/:ticker" element={<StockDetailPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </Box>
      </Box>
    </>
  );
}

export function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <ProtectedApp />
        <Toaster />
      </AuthProvider>
    </ErrorBoundary>
  );
}
