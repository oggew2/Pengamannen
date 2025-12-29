# Börslabbet App - Improvements & TODOs

## Completed ✅

### Data Quality
- [x] Add data validation on EODHD fetch (check for nulls, outliers)
- [x] Implement data freshness checks before running strategies
- [x] Health check with DB connectivity

### Performance
- [x] Cache strategy calculations (invalidate on data update)
- [x] Cache statistics and invalidation endpoints

### Backtesting
- [x] Add transaction costs (0.1% per trade)
- [x] Implement slippage modeling (0.05%)
- [x] Calculate Sortino ratio

## In Progress 🔄

### Strategy Accuracy
- [ ] Implement full Piotroski F-Score (9 criteria) when more data available
- [ ] Add momentum skip-month (exclude last month to avoid mean reversion)

### Backtesting
- [ ] Add benchmark comparison (OMXS30)
- [ ] Calculate rolling Sharpe, Sortino ratios

## Planned 📋

### Frontend
- [ ] Add loading states for all API calls
- [ ] Implement error boundaries
- [ ] Add stock detail modal with charts
- [ ] Mobile-responsive improvements

### Monitoring
- [ ] Add Prometheus metrics endpoint
- [ ] Add API rate limiting
- [ ] Log slow queries

### Features
- [ ] Email alerts for rebalance dates
- [ ] Export portfolio to CSV/Excel
- [ ] Compare multiple backtests
- [ ] Custom strategy builder

### Infrastructure
- [ ] Docker containerization
- [ ] CI/CD pipeline
- [ ] Database migrations with Alembic
- [ ] Environment-specific configs

## Known Limitations

1. **EODHD Free Tier**: 20 API calls/day limits data freshness
2. **F-Score Approximation**: Using 4 criteria instead of full 9
3. **No Real-time Data**: EOD prices only
4. **Swedish Stocks Only**: Hardcoded OMX Stockholm universe
