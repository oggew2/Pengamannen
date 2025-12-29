import { Routes, Route } from 'react-router-dom';
import { Navigation } from './components/Navigation';
import { Dashboard } from './pages/Dashboard';
import { StrategyPage } from './pages/StrategyPage';
import { PortfolioPage } from './pages/PortfolioPage';
import { CombinerPage } from './pages/CombinerPage';
import { BacktestingPage } from './pages/BacktestingPage';
import { HistoricalBacktestPage } from './pages/HistoricalBacktestPage';
import { NotFound } from './pages/NotFound';
import styles from './styles/App.module.css';

export function App() {
  return (
    <>
      <Navigation />
      <main className={`${styles.main} ${styles.container}`}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/strategies/:type" element={<StrategyPage />} />
          <Route path="/portfolio/sverige" element={<PortfolioPage />} />
          <Route path="/portfolio/combiner" element={<CombinerPage />} />
          <Route path="/backtesting" element={<BacktestingPage />} />
          <Route path="/backtesting/historical" element={<HistoricalBacktestPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </>
  );
}
