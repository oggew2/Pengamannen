import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Box, Flex, Text } from '@chakra-ui/react';
import { Suspense, lazy } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Navigation } from './components/Navigation';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Dashboard } from './pages/Dashboard';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { Toaster } from './components/toaster';
import { PageTransition } from './components/Animations';

// Lazy load pages
const StockDetailPage = lazy(() => import('./pages/StockDetailPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
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

function AnimatedRoutes() {
  const location = useLocation();
  
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<PageTransition><Dashboard /></PageTransition>} />
        <Route path="/settings" element={<PageTransition><SettingsPage /></PageTransition>} />
        <Route path="/data" element={<PageTransition><DataManagementPage /></PageTransition>} />
        <Route path="/stock/:ticker" element={<PageTransition><StockDetailPage /></PageTransition>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  );
}

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
            <AnimatedRoutes />
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
