import { Routes, Route, Navigate } from 'react-router-dom';
import { Box } from '@chakra-ui/react';
import { Suspense, lazy } from 'react';
import { Navigation } from './components/Navigation';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Dashboard } from './pages/Dashboard';

// Lazy load pages
const StrategyPage = lazy(() => import('./pages/StrategyPage').then(m => ({ default: m.StrategyPage })));
const PortfolioPage = lazy(() => import('./pages/PortfolioPage').then(m => ({ default: m.PortfolioPage })));
const CombinerPage = lazy(() => import('./pages/CombinerPage').then(m => ({ default: m.CombinerPage })));
const BacktestingPage = lazy(() => import('./pages/BacktestingPage').then(m => ({ default: m.BacktestingPage })));
const HistoricalBacktestPage = lazy(() => import('./pages/HistoricalBacktestPage').then(m => ({ default: m.HistoricalBacktestPage })));
const AnalyticsDashboard = lazy(() => import('./pages/AnalyticsDashboard'));
const GoalsPage = lazy(() => import('./pages/GoalsPage'));
const StockDetailPage = lazy(() => import('./pages/StockDetailPage'));
const MyPortfolioPage = lazy(() => import('./pages/MyPortfolioPage'));
const StrategyComparisonPage = lazy(() => import('./pages/StrategyComparisonPage'));
const DividendCalendarPage = lazy(() => import('./pages/DividendCalendarPage'));
const CostAnalysisPage = lazy(() => import('./pages/CostAnalysisPage'));
const PortfolioAnalysisPage = lazy(() => import('./pages/PortfolioAnalysisPage'));
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

export function App() {
  return (
    <ErrorBoundary>
      <Navigation />
      {/* Main content area - offset for sidebar on desktop */}
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
              <Route path="/portfolio/sverige" element={<PortfolioPage />} />
              <Route path="/portfolio/combiner" element={<CombinerPage />} />
              <Route path="/portfolio/my" element={<MyPortfolioPage />} />
              <Route path="/portfolio/analysis" element={<PortfolioAnalysisPage />} />
              <Route path="/backtesting" element={<BacktestingPage />} />
              <Route path="/backtesting/historical" element={<HistoricalBacktestPage />} />
              <Route path="/analytics" element={<AnalyticsDashboard />} />
              <Route path="/goals" element={<GoalsPage />} />
              <Route path="/compare" element={<StrategyComparisonPage />} />
              <Route path="/dividends" element={<DividendCalendarPage />} />
              <Route path="/costs" element={<CostAnalysisPage />} />
              <Route path="/rebalancing" element={<MinStrategiPage />} />
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
    </ErrorBoundary>
  );
}
