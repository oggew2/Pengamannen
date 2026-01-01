# Min Strategi - Unified Portfolio Dashboard

## Overview

A single unified dashboard where users can select which strategies they follow and see all recommended actions in one place. Replaces the current Rebalancing page with a more comprehensive solution.

## Problem Statement

Currently, users following multiple strategies must:
1. Check each strategy page separately
2. Manually track which stocks to buy/sell
3. Compare against their holdings mentally
4. Remember rebalancing dates for each strategy

## Solution

One page that:
- Lets users tick which strategies they follow (1-4)
- Shows ALL target stocks from selected strategies
- Compares against imported holdings (CSV)
- Groups actions by urgency (SELL NOW → SELL SOON → BUY → HOLD)
- Shows timing for each action

---

## User Flow

```
1. User selects strategies (checkboxes, persisted)
         ↓
2. System fetches top 10 from each selected strategy
         ↓
3. System compares against user's imported holdings
         ↓
4. System generates action list with timing
         ↓
5. User sees unified view of all actions needed
```

---

## UI Design

### Design Principles (from our design system)

- Dark theme (gray.700, gray.800 backgrounds)
- Brand color for accents (brand.500 = blue)
- Rounded corners (8px cards, 6px buttons)
- Subtle borders (gray.600)
- Clean typography (gray.50 headings, gray.300 body)
- Smooth transitions (150ms)

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│  Header: "Min Strategi"                                         │
│  Subtitle: "Välj strategier och se alla rekommendationer"       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STRATEGY SELECTOR (horizontal pills, multi-select)             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │ ● Momentum  │ │ ● Värde     │ │ ○ Utdelning │ │ ○ Kvalitet│ │
│  │   (blue)    │ │   (green)   │ │   (purple)  │ │   (orange)│ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SUMMARY CARDS (4 cards in a row)                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐ │
│  │  20          │ │  18          │ │  5           │ │  3     │ │
│  │  Målaktier   │ │  Har du      │ │  Köp         │ │  Sälj  │ │
│  │  gray.600 bg │ │  gray.600 bg │ │  green tint  │ │ red    │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────┘ │
│                                                                 │
│  Next rebalance: "Momentum ombalanseras om 45 dagar (15 mar)"   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ACTION SECTIONS (collapsible, sorted by urgency)               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 🔴 SÄLJ NU (3)                                    [Expand ▼]││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ ┌─────────────────────────────────────────────────────────┐ ││
│  │ │ VOLV B                                                  │ ││
│  │ │ Föll ur Momentum dec 2025                    [blue tint]│ ││
│  │ │ Värde: 15 230 kr                                        │ ││
│  │ └─────────────────────────────────────────────────────────┘ ││
│  │ ┌─────────────────────────────────────────────────────────┐ ││
│  │ │ ERIC B                                                  │ ││
│  │ │ Föll ur Värde mar 2025                      [green tint]│ ││
│  │ │ Värde: 8 500 kr                                         │ ││
│  │ └─────────────────────────────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 🟡 SÄLJ VID OMBALANSERING (2)                   [Expand ▼] ││
│  │ ... stocks that will fall out at next rebalance            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 🟢 KÖP (5)                                      [Expand ▼] ││
│  │ ... stocks to buy with amounts                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ✓ BEHÅLL (15)                                   [Expand ▼] ││
│  │ ... stocks that are correctly held                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FULL COMPARISON TABLE (optional, collapsed by default)         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Visa fullständig lista                          [Expand ▼] ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ Ticker   Strategi    Status   Mål      Har      Diff       ││
│  │ ──────────────────────────────────────────────────────────  ││
│  │ LUG      Momentum    KÖP      12.5k    0        +12.5k     ││
│  │ SSAB B   Momentum    OK       12.5k    13.2k    +0.7k      ││
│  │ SSAB B   Utdelning   OK       12.5k    13.2k    +0.7k      ││
│  │ VOLV B   -           SÄLJ     0        15.2k    -15.2k     ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Strategy Colors

Each strategy has a distinct color for visual identification:

| Strategy | Color | Hex | Usage |
|----------|-------|-----|-------|
| Momentum | Blue | #4299E1 | Left border, subtle bg tint |
| Värde | Green | #48BB78 | Left border, subtle bg tint |
| Utdelning | Purple | #9F7AEA | Left border, subtle bg tint |
| Kvalitet | Orange | #ED8936 | Left border, subtle bg tint |

Card styling with strategy color:
```css
/* Example: Momentum stock card */
background: rgba(66, 153, 225, 0.08);  /* Very subtle blue tint */
border-left: 3px solid #4299E1;         /* Solid blue left border */
```

---

## Action Categories

### 1. 🔴 SÄLJ NU (Sell Now)
- Stocks in holdings but NOT in any selected strategy's current top 10
- Already fell out of the list at a past rebalance date
- **Urgency:** High - should have been sold already

### 2. 🟡 SÄLJ VID OMBALANSERING (Sell at Rebalance)
- Stocks in holdings AND in strategy, but rank has dropped significantly (e.g., below #15)
- Will likely fall out at next rebalance
- **Urgency:** Medium - sell at next rebalance date

### 3. 🟢 KÖP (Buy)
- Stocks in strategy's top 10 but NOT in holdings
- Shows calculated amount based on equal-weight allocation
- **Urgency:** Medium - buy to complete portfolio

### 4. ✓ BEHÅLL (Hold)
- Stocks in BOTH strategy's top 10 AND holdings
- Portfolio is correctly aligned
- **Urgency:** None - no action needed

---

## Data Requirements

### From Backend
```typescript
// For each selected strategy
GET /v1/strategies/{name}
→ Returns top 10 stocks with rank, score, ticker, name

// Rebalance dates
GET /v1/portfolio/rebalance-dates
→ Returns next rebalance date per strategy
```

### From Frontend (localStorage)
```typescript
// User's holdings (from CSV import)
localStorage.getItem('myHoldings')
→ [{ ticker: "VOLV B", shares: 50, avgPrice: 250 }, ...]

// Selected strategies
localStorage.getItem('selectedStrategies')
→ ["sammansatt_momentum", "trendande_varde"]
```

---

## Calculation Logic

### Target Holdings
```typescript
function getTargetHoldings(selectedStrategies: string[]) {
  const targets = [];
  for (const strategy of selectedStrategies) {
    const top10 = await fetchStrategy(strategy);
    for (const stock of top10) {
      targets.push({
        ticker: stock.ticker,
        name: stock.name,
        strategy: strategy,
        rank: stock.rank,
      });
    }
  }
  return targets; // May have duplicates if stock in multiple strategies
}
```

### Action Generation
```typescript
function generateActions(targets, holdings, portfolioValue) {
  const actions = [];
  const targetTickers = new Set(targets.map(t => t.ticker));
  const holdingTickers = new Set(holdings.map(h => h.ticker));
  
  // SELL: In holdings but not in targets
  for (const holding of holdings) {
    if (!targetTickers.has(holding.ticker)) {
      actions.push({
        type: 'SELL_NOW',
        ticker: holding.ticker,
        value: holding.shares * currentPrice,
        reason: 'Inte längre i någon vald strategi'
      });
    }
  }
  
  // BUY: In targets but not in holdings
  for (const target of targets) {
    if (!holdingTickers.has(target.ticker)) {
      const targetValue = portfolioValue / targets.length;
      actions.push({
        type: 'BUY',
        ticker: target.ticker,
        strategy: target.strategy,
        targetValue: targetValue,
        reason: `Ny i ${strategyName} - köp ${formatSEK(targetValue)}`
      });
    }
  }
  
  // HOLD: In both
  for (const target of targets) {
    if (holdingTickers.has(target.ticker)) {
      actions.push({
        type: 'HOLD',
        ticker: target.ticker,
        strategy: target.strategy,
        rank: target.rank,
        reason: `Rank #${target.rank} - behåll`
      });
    }
  }
  
  return actions;
}
```

---

## Component Structure

```
MinStrategiPage/
├── StrategySelector        # Horizontal pill buttons, multi-select
├── SummaryCards            # 4 stat cards (target, have, buy, sell)
├── NextRebalanceInfo       # Text showing next rebalance dates
├── ActionSection           # Collapsible section for each action type
│   ├── ActionHeader        # "🔴 SÄLJ NU (3)" with expand button
│   └── ActionCard          # Individual stock card with strategy color
├── ComparisonTable         # Full table view (collapsed by default)
└── EmptyState              # Shown when no strategies selected
```

---

## Interactions

### Strategy Selection
- Click pill to toggle selection
- Selected = filled with brand color + checkmark
- Unselected = gray.600 background, gray.300 text
- Selection persisted to localStorage immediately
- Page re-renders with new data on change

### Action Sections
- Default: SÄLJ NU and KÖP expanded, others collapsed
- Click header to expand/collapse
- Smooth height animation (200ms)
- Badge shows count in header

### Stock Cards
- Hover: Slight background lighten
- Click: Navigate to stock detail page
- Strategy color: Left border + subtle background tint

---

## Empty States

### No Strategies Selected
```
┌─────────────────────────────────────────┐
│                                         │
│     📊                                  │
│                                         │
│     Välj strategier ovan                │
│     för att se rekommendationer         │
│                                         │
└─────────────────────────────────────────┘
```

### No Holdings Imported
```
┌─────────────────────────────────────────┐
│                                         │
│     📁                                  │
│                                         │
│     Importera dina innehav              │
│     för att se köp/sälj-rekommendationer│
│                                         │
│     [Importera CSV]                     │
│                                         │
└─────────────────────────────────────────┘
```

---

## Mobile Responsiveness

- Strategy pills: Wrap to 2x2 grid on mobile
- Summary cards: 2x2 grid on mobile
- Action cards: Full width, stacked
- Table: Horizontal scroll or simplified view

---

## Technical Notes

### Performance
- Fetch all selected strategies in parallel
- Memoize calculations when inputs don't change
- Lazy load comparison table (only render when expanded)

### State Management
- Strategy selection: localStorage + React state
- Holdings: localStorage (from MyPortfolioPage CSV import)
- Strategy data: Fetched on mount and when selection changes

### Persistence
- `selectedStrategies`: string[] in localStorage
- Survives page refresh and browser close
- User can always change selection

---

## Migration Plan

1. Create new `MinStrategiPage.tsx`
2. Update route from `/rebalancing` to use new page
3. Keep old `RebalancingPage.tsx` as backup temporarily
4. Update navigation label from "Rebalansering" to "Min Strategi"
5. Remove old page after confirming new one works

---

## Success Metrics

- User can see all actions in < 3 seconds
- Clear visual distinction between action types
- No confusion about which strategy a stock belongs to
- Timing information helps user prioritize actions
