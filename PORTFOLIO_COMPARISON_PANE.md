# Portfolio Comparison Pane - API Documentation

## Overview
New toggleable portfolio comparison pane that shows current portfolio against all 4 Börslabbet strategies simultaneously.

## API Endpoint

### POST `/portfolio/compare-all-strategies`

**Purpose**: Compare current portfolio against all strategies with rebalance timing

**Request Body**:
```json
[
  {"ticker": "ERIC-B", "shares": 100},
  {"ticker": "VOLV-B", "shares": 50},
  {"ticker": "ASSA-B", "shares": 75}
]
```

**Response**:
```json
{
  "success": true,
  "portfolio_overview": {
    "timestamp": "2025-12-30T12:25:14.047+01:00",
    "summary": {
      "total_strategies": 4,
      "strategies_due_for_rebalance": 1,
      "high_drift_strategies": 2,
      "next_rebalance_days": 15
    },
    "strategy_comparisons": [
      {
        "strategy_name": "sammansatt_momentum",
        "display_name": "Sammansatt Momentum",
        "next_rebalance_date": "2026-03-01",
        "days_until_rebalance": 61,
        "current_drift_percentage": 15.5,
        "recommendation": "HIGH_DRIFT",
        "suggested_changes": {
          "buy": [{"ticker": "INVE-B", "action": "BUY", "reason": "Top momentum pick"}],
          "sell": [{"ticker": "OLD-STOCK", "action": "SELL", "reason": "No longer in top 20"}],
          "keep": [{"ticker": "ERIC-B", "action": "KEEP", "reason": "Still in top picks"}]
        },
        "is_rebalance_due": false
      },
      {
        "strategy_name": "trendande_varde",
        "display_name": "Trendande Värde", 
        "next_rebalance_date": "2026-01-01",
        "days_until_rebalance": 2,
        "current_drift_percentage": 25.8,
        "recommendation": "REBALANCE_NOW",
        "suggested_changes": {
          "buy": [...],
          "sell": [...],
          "keep": [...]
        },
        "is_rebalance_due": true
      }
    ]
  },
  "features": {
    "multi_strategy_comparison": true,
    "rebalance_scheduling": true,
    "drift_monitoring": true,
    "toggleable_pane": true
  }
}
```

## Frontend Integration

### UI Components Needed:

1. **Toggle Button**: Show/hide comparison pane
2. **Strategy Cards**: One card per strategy showing:
   - Strategy name and next rebalance date
   - Days until rebalance (with urgency colors)
   - Current drift percentage
   - Recommendation badge
   - Expandable suggested changes

3. **Summary Panel**: 
   - Total strategies tracked
   - Number due for rebalance
   - Next upcoming rebalance

### Visual Design:

```
┌─ Portfolio Comparison Pane ─────────────────┐
│ [Toggle On/Off] Summary: 1 due, next in 2d │
│                                             │
│ ┌─ Sammansatt Momentum ──────────────────┐  │
│ │ Next: 2026-03-01 (61 days)             │  │
│ │ Drift: 15.5% [HIGH_DRIFT]              │  │
│ │ [▼] Show Changes (3 buy, 1 sell)       │  │
│ └─────────────────────────────────────────┘  │
│                                             │
│ ┌─ Trendande Värde ──────────────────────┐  │
│ │ Next: 2026-01-01 (2 days) ⚠️           │  │
│ │ Drift: 25.8% [REBALANCE_NOW]           │  │
│ │ [▼] Show Changes (5 buy, 3 sell)       │  │
│ └─────────────────────────────────────────┘  │
│                                             │
│ ... (other strategies)                      │
└─────────────────────────────────────────────┘
```

### Color Coding:
- **Green**: ON_TRACK (drift < 10%)
- **Yellow**: HIGH_DRIFT (drift 10-20%)
- **Orange**: REBALANCE_SOON (< 7 days)
- **Red**: REBALANCE_NOW (overdue or high drift + due soon)

## Implementation Status

✅ **Backend**: Portfolio comparison service implemented
✅ **API**: Endpoint `/portfolio/compare-all-strategies` ready
✅ **Data**: All 4 strategies with rebalance schedules
✅ **Logic**: Drift calculation and trade suggestions
✅ **Timing**: Next rebalance date calculation

🔄 **Frontend**: Ready for integration
- Add toggle button to main portfolio view
- Create comparison pane component
- Implement strategy cards with expandable changes
- Add color coding for urgency levels

## Benefits

1. **Always Visible**: Users can see all strategies at once
2. **Time Awareness**: Clear countdown to next rebalances
3. **Drift Monitoring**: Visual indication of portfolio drift
4. **Actionable**: Specific buy/sell suggestions for each strategy
5. **Toggleable**: Can be hidden when not needed
6. **Comprehensive**: All strategies in one view vs individual analysis
