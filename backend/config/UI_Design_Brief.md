# UI/UX Design Brief: Börslabbet Clone - Modern Fintech Dashboard

**Document Version:** 1.0  
**Date:** December 30, 2025  
**Target Audience:** React developers, UI engineers, designers  
**Design Philosophy:** Minimalist, data-focused, dark-mode optimized, mobile-first
Important: No shortcuts or mock data. dont remove existing functionality - if it's not covered here you adapt it to this style.

---

## Table of Contents

1. [Visual Vision & Design Principles](#visual-vision--design-principles)
2. [Color System](#color-system)
3. [Typography](#typography)
4. [Spacing & Layout](#spacing--layout)
5. [Interactive Components](#interactive-components)
6. [Page/Screen Components](#pagescreen-components)
   - [Dashboard (Main)](#dashboard-main)
   - [Rebalancing](#rebalancing)
   - [Holdings Detail](#holdings-detail)
   - [Strategies](#strategies)
   - [Portfolio Analysis](#portfolio-analysis)
   - [Alerts & Notifications](#alerts--notifications)
   - [Settings & Preferences](#settings--preferences)
   - [Generic Page Template](#generic-page-template)
7. [Interactive Behaviors & Micro-Interactions](#interactive-behaviors--micro-interactions)
8. [Mobile Responsiveness](#mobile-responsiveness)
9. [Tech Stack Recommendations](#tech-stack-recommendations)
10. [Accessibility & Performance](#accessibility--performance)

---

## Visual Vision & Design Principles

### Overall Aesthetic
Create a **modern, minimalist fintech dashboard** inspired by 2025 design trends:
- Clean, spacious layouts (Robinhood + Betterment aesthetic)
- Dark mode as primary (reduce eye strain, professional look)
- Data visualization-first (charts prioritized over raw numbers)
- Mobile-first responsive design
- Subtle micro-interactions for user feedback (smooth transitions, loading states)
- Professional yet approachable (not corporate, not playful)

### Core Values
- **Trust**: Clear data presentation, no hidden information
- **Efficiency**: Minimal clicks to complete tasks
- **Clarity**: Users understand their portfolio at a glance
- **Responsiveness**: Real-time feedback, smooth animations
- **Accessibility**: WCAG 2.1 AA compliant, keyboard navigation supported

---

## Color System

### Primary Colors

| Color | Value | Usage | Contrast |
|-------|-------|-------|----------|
| **Dark Background** | `#0f1419` | Main app background | - |
| **Card Surface** | `#1a1f2e` | Card backgrounds, modals | 4.5:1 |
| **Primary Teal** | `#00b4d8` | Buttons, links, accents | 4.5:1 |
| **Primary Teal Hover** | `#00a3c0` | Button hover state | 4.5:1 |
| **Primary Teal Active** | `#0090ad` | Button active state | 4.5:1 |

### Semantic Colors

| Name | Dark Mode | Light Mode | Usage |
|------|-----------|-----------|-------|
| **Success** | `#10b981` | `#059669` | Gains, positive changes, confirmations |
| **Success Light** | `#10b98133` | `#10b98120` | Success backgrounds, highlights |
| **Error** | `#ef4444` | `#dc2626` | Losses, errors, alerts |
| **Error Light** | `#ef444433` | `#ef444420` | Error backgrounds, highlights |
| **Warning** | `#f59e0b` | `#d97706` | Warnings, cautions |
| **Warning Light** | `#f59e0b33` | `#f59e0b20` | Warning backgrounds |
| **Info** | `#3b82f6` | `#1d4ed8` | Information, notifications |
| **Info Light** | `#3b82f633` | `#3b82f620` | Info backgrounds |

### Text Colors

| Element | Dark Mode | Light Mode | Contrast |
|---------|-----------|-----------|----------|
| **Heading 1-3** | `#f5f5f5` | `#0f1419` | 16:1 |
| **Body Text** | `#d1d5db` | `#374151` | 7:1 |
| **Secondary Text** | `#9ca3af` | `#6b7280` | 4.5:1 |
| **Disabled Text** | `#4b5563` | `#9ca3af` | 3:1 |

### Gradient Accents
- **Profit Gradient**: `linear-gradient(135deg, #10b981, #06b6d4)`
- **Loss Gradient**: `linear-gradient(135deg, #ef4444, #f97316)`
- **Neutral Gradient**: `linear-gradient(135deg, #3b82f6, #8b5cf6)`

### Dark Mode Implementation
```css
/* Preferred: Use CSS variables for easy switching */
:root {
  --color-bg-primary: #0f1419;
  --color-bg-secondary: #1a1f2e;
  --color-text-primary: #f5f5f5;
  --color-text-secondary: #d1d5db;
  --color-text-tertiary: #9ca3af;
  --color-primary: #00b4d8;
  --color-success: #10b981;
  --color-error: #ef4444;
  --color-warning: #f59e0b;
  --color-info: #3b82f6;
  --color-border: #2d3748;
}

[data-theme="light"] {
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f8f9fa;
  --color-text-primary: #0f1419;
  /* ... etc */
}
```

---

## Typography

### Font Stack
```css
/* Headings: Modern sans-serif */
--font-headings: "Geist", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;

/* Body: Clear, legible */
--font-body: "Geist", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;

/* Numbers/Data: Monospace for prices */
--font-mono: "JetBrains Mono", "Courier New", monospace;
```

### Type Scale

| Element | Size | Weight | Line Height | Usage |
|---------|------|--------|-------------|-------|
| **H1** | 32px | 600 | 1.2 | Page titles, major sections |
| **H2** | 24px | 600 | 1.3 | Section headers, card titles |
| **H3** | 20px | 600 | 1.4 | Subsections, strategy names |
| **H4** | 16px | 600 | 1.5 | Card headers, labels |
| **Body** | 14px | 400 | 1.5 | Regular text, descriptions |
| **Small** | 12px | 400 | 1.6 | Help text, metadata, timestamps |
| **Code/Numbers** | 14px | 500 | 1.5 | Prices, stock symbols, data |
| **Button** | 14px | 500 | 1.5 | All buttons, CTAs |

### Font Weight Usage
- **400** (Regular): Body text, descriptions
- **500** (Medium): Labels, buttons, secondary headings
- **600** (Semibold): Headings, emphasis, data values

### Letter Spacing
- Headings: `-0.01em` (tighter)
- Body: `0` (normal)
- Code: `0.05em` (slightly wider)

---

## Spacing & Layout

### 8px Grid System
All spacing follows multiples of 8px for consistency:

| Token | Value | Usage |
|-------|-------|-------|
| **xs** | 4px | Small gaps between inline elements |
| **sm** | 8px | Button padding, small gaps |
| **md** | 16px | Card padding, section gaps |
| **lg** | 24px | Major section gaps |
| **xl** | 32px | Top-level layout gaps |
| **2xl** | 48px | Full-height sections, large containers |

### Layout Structure

**Desktop (1200px+)**
```
┌─────────────────────────────────────────────────┐
│  Header / Navigation (56px height)              │
├──────────────────┬──────────────────────────────┤
│  Sidebar         │  Main Content Area           │
│  (240px)         │  (max-width: 1000px centered)│
│                  │                              │
│                  └──────────────────────────────┘
└──────────────────┴──────────────────────────────┘
```

**Tablet (768px - 1199px)**
```
┌──────────────────────────────────────┐
│  Header (collapsible sidebar)         │
├──────────────────────────────────────┤
│  Full-width content                  │
│  (Sidebar drawer on hamburger menu)  │
└──────────────────────────────────────┘
```

**Mobile (<768px)**
```
┌──────────────────┐
│  Header (48px)   │
├──────────────────┤
│  Full-width      │
│  content         │
│  (stacked)       │
├──────────────────┤
│  Bottom Nav      │
│  (56px)          │
└──────────────────┘
```

### Container Sizes
- **xs**: 320px (mobile)
- **sm**: 640px (tablet)
- **md**: 768px (small desktop)
- **lg**: 1024px (desktop)
- **xl**: 1280px (wide desktop)
- **Max Content**: 1000px (centered with side padding)

### Padding/Margin Guidelines
- Cards: 24px (lg) padding
- Section headers: 32px (xl) top margin
- Form groups: 16px (md) gap
- Button groups: 8px (sm) gap
- List items: 12px vertical, 16px horizontal

---

## Interactive Components

### Buttons

#### Button States
```
Normal      Hover       Active      Disabled
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Submit │ │ Submit │ │ Submit │ │ Submit │
└────────┘ └────────┘ └────────┘ └────────┘
#00b4d8   #00a3c0   #0090ad   #4b5563 (60%)
```

#### Button Variants

| Variant | Background | Text | Border | Usage |
|---------|-----------|------|--------|-------|
| **Primary** | `#00b4d8` | White | None | Main actions (submit, save) |
| **Secondary** | `#2d3748` | `#d1d5db` | `1px #404d64` | Alternative actions |
| **Tertiary** | Transparent | `#00b4d8` | `1px #00b4d8` | Low-priority actions |
| **Ghost** | Transparent | `#d1d5db` | None | Minimal actions |
| **Danger** | `#ef4444` | White | None | Destructive actions (delete) |
| **Success** | `#10b981` | White | None | Confirmation, completion |

#### Button Sizes
- **lg**: 48px height, 20px horizontal padding (desktop CTA)
- **md**: 40px height, 16px horizontal padding (standard)
- **sm**: 32px height, 12px horizontal padding (inline, secondary)
- **xs**: 24px height, 8px horizontal padding (compact)

#### Button Properties
- Border radius: `8px`
- Transition: `all 150ms cubic-bezier(0.16, 1, 0.3, 1)`
- Hover: Darken by 10%, lift 2px (translateY -2px, shadow)
- Active: Darken by 20%, press down (translateY 0)
- Disabled: 60% opacity, no cursor change

### Input Fields

#### Input States
```
Empty       Focused     Filled      Error       Disabled
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│        │ │ cursor │ │ value  │ │ error! │ │ value  │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘
gray      teal      gray      red        gray (60%)
```

#### Input Properties
- Height: 40px
- Padding: 12px
- Border: `1px solid #2d3748` (empty), `2px solid #00b4d8` (focused)
- Border radius: `6px`
- Font: 14px, body font
- Placeholder: `#4b5563` (secondary text)
- Transition: `border-color 150ms`
- Error state: Border `2px solid #ef4444`, error message 12px red below

### Cards

#### Card States
```
Resting         Hover           Active
┌──────────┐   ┌──────────┐   ┌──────────┐
│          │   │  lifted  │   │ clicked  │
│ Content  │   │ Content  │   │ Content  │
│          │   │          │   │          │
└──────────┘   └──────────┘   └──────────┘
```

#### Card Properties
- Background: `#1a1f2e`
- Border: `1px solid #2d3748`
- Border radius: `8px`
- Padding: 24px (md)
- Box shadow: `0 1px 3px rgba(0,0,0,0.1)` (resting)
- Hover: 
  - Box shadow: `0 10px 25px rgba(0,0,0,0.2)`
  - Transform: `translateY(-4px)`
  - Transition: `all 200ms cubic-bezier(0.16, 1, 0.3, 1)`
- Active: `box-shadow: 0 4px 12px rgba(0,0,0,0.15)`

### Modals

#### Modal Properties
- Backdrop: `rgba(0, 0, 0, 0.6)` (blur 4px)
- Dialog: Centered, max-width 500px
- Animation: Fade in 250ms, scale from 95%
- Close button: Top-right corner, 32px
- Padding: 32px (xl)
- Border radius: 12px
- Transition: Smooth fade-out on close

### Toggles & Switches

#### Toggle Properties
- Width: 44px, Height: 24px
- Border radius: `12px`
- Background (off): `#2d3748`
- Background (on): `#00b4d8`
- Knob: 20px circle, white, shadow
- Transition: `all 200ms`
- Click target: Full 44x24 area

### Loading States

#### Skeleton Screens (Preferred over spinners)
```css
.skeleton {
  background: linear-gradient(
    90deg,
    #2d3748 0%,
    #404d64 50%,
    #2d3748 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

- Use skeleton loaders for content blocks
- Not spinners (spinners feel slow)
- Maintain layout to prevent CLS (Cumulative Layout Shift)

### Tooltips

#### Tooltip Properties
- Background: `#2d3748` with 95% opacity
- Text: `#d1d5db`, 12px, medium weight
- Padding: 8px 12px
- Border radius: 4px
- Arrow: 4px triangle pointing to target
- Appear: On hover, 300ms delay
- Disappear: Immediate on mouse out
- Max width: 200px, word wrapping enabled

---

## Page/Screen Components

### Dashboard (Main)

**Purpose**: Overview of all portfolios and strategies  
**Primary users**: Daily check-in, quick monitoring

**Layout**:
```
┌─────────────────────────────────────────────┐
│ Portfolio Summary Card                      │
│ ┌─────────────────────────────────────────┐ │
│ │ Total Value: 450,230 kr                 │ │ ← Large, bold
│ │ YTD Return: +12.3%    YTD Gain: +50,230│ │ ← Key metrics
│ │                                          │ │
│ │ [6M] [1Y] [3Y] [ALL] [Custom Range]    │ │ ← Period selectors
│ │                                          │ │
│ │ [Interactive Line Chart]                │ │ ← Responsive, draggable
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Strategy Performance Grid (2x2)             │
│ ┌──────────────────┐ ┌──────────────────┐  │
│ │ Momentum         │ │ Trendande Värde  │  │
│ │ +15.2% YTD       │ │ +8.9% YTD        │  │
│ │ 10 holdings      │ │ 10 holdings      │  │
│ │ ▲ +2.1% 1M       │ │ ▼ -0.5% 1M       │  │
│ └──────────────────┘ └──────────────────┘  │
│ ┌──────────────────┐ ┌──────────────────┐  │
│ │ Trendande Utd.   │ │ Trendande Kvalit │  │
│ │ +7.3% YTD        │ │ +10.5% YTD       │  │
│ │ 10 holdings      │ │ 10 holdings      │  │
│ │ ▲ +1.2% 1M       │ │ ▲ +3.8% 1M       │  │
│ └──────────────────┘ └──────────────────┘  │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Recent Holdings (Sortable Table)            │
│                                             │
│ Symbol │ Strategy │ Price │ Change │ 1M %  │
│ ADD    │ Värde    │ 142.5 │ +1.2% │ +3.2%│
│ SAAB   │ Momentum │ 185.0 │ +2.5% │ +8.1%│
│ VOLVA  │ Utdelning│ 28.50 │ -0.3% │ -1.2%│
│ ...    │ ...      │ ...   │ ...   │ ...  │
│                                             │
│ [View All] [Export]                         │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Quick Actions / Upcoming Events             │
│ ⏱️  Rebalancing: Q1 in 45 days (March 31)  │
│ 📊 Next dividend payment: 2 holdings in 15d │
│ 🎯 Strategy alerts: Momentum top 40 updated │
│                                             │
│ [Manage Alerts] [View Calendar]             │
└─────────────────────────────────────────────┘
```

**Key Features**:
- Real-time portfolio value (update every 15 seconds)
- Interactive chart (hover for value on date, draggable range selector)
- Strategy cards clickable to drill down
- Holdings table sortable by any column
- Color coding: Green for gains, red for losses, neutral gray for neutral

---

### Rebalancing

**Purpose**: Manage upcoming rebalancing dates, see what changes, execute rebalance  
**Primary users**: Monthly planning, pre-rebalancing checklist

**Layout**:
```
┌──────────────────────────────────────────────┐
│ Rebalancing Calendar                         │
│                                              │
│ Next: Q1 2025 Rebalancing                   │
│ 📅 March 31, 2025  |  ⏱️ 45 days away        │
│                                              │
│ [Quarterly] [Annual] [Custom]                │
│ Jan Feb Mar Apr May Jun Jul Aug Sep Oct...   │
│            ↑↑↑ (March highlighted)          │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│ Changes Overview                             │
│                                              │
│ Sammansatt Momentum: 4 changes               │
│ ✓ SAAB (keep)   • ADD (sell)   • ABC (buy)  │
│ • VOLVA (sell)  • XYZ (buy)                 │
│                                              │
│ Trendande Värde: 2 changes                  │
│ ✓ HEXAGON (keep) • AAA (sell)  • BBB (buy) │
│                                              │
│ Trendande Utdelning: 1 change               │
│ ✓ No changes                                 │
│                                              │
│ Trendande Kvalitet: 3 changes               │
│ ✓ HANDELSBANKEN (keep) • CCC (sell)        │
│ • DDD (buy)  • EEE (buy)                    │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│ Actions Required                             │
│                                              │
│ SELL (8 stocks):                            │
│ [ ] ADD       (142 kr)  [Copy ISIN]         │
│ [ ] VOLVA     (28.50 kr) [Copy ISIN]        │
│ [ ] AAA       (...)      [Copy ISIN]        │
│ ... (5 more)                                │
│                                              │
│ BUY (6 stocks):                             │
│ [ ] ABC       (...)      [Copy ISIN]        │
│ [ ] XYZ       (...)      [Copy ISIN]        │
│ [ ] BBB       (...)      [Copy ISIN]        │
│ ... (3 more)                                │
│                                              │
│ [Expand Details] [Export List] [Share]      │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│ Cost Analysis                                │
│                                              │
│ 💰 Est. Trading Cost: ~0.5% (500 kr)       │
│    • Spread: 0.2%                           │
│    • Courtage: 0.05% (Avanza)               │
│    • Market Impact: 0.25%                   │
│                                              │
│ 💡 Best Broker Today:                       │
│    Avanza: 0.09% fee                        │
│    Nordnet: 0.15% fee                       │
│                                              │
│ 📊 Comparison (annual impact):              │
│    4 rebalances × 0.5% = 2% annual cost    │
│    vs. passive index (~0.05% cost)          │
│                                              │
│ [Set Reminder] [Schedule Trade] [Simulate] │
└──────────────────────────────────────────────┘
```

**Key Features**:
- Countdown to next rebalancing
- Visual breakdown by strategy
- ISIN copy-to-clipboard for quick trades
- Cost transparency (real-time spread estimates)
- Broker comparison (cheapest courtage)
- Historical rebalancing audit log

---

### Holdings Detail

**Purpose**: Deep dive into individual stock, understand allocation, see alerts  
**Primary users**: Research, monitoring specific positions

**Layout**:
```
┌────────────────────────────────────────────┐
│ ADD (Addtech)                              │
│ Trendande Värde Strategy                   │
│ ISIN: SE0000872219 | GICS: Industrials    │
│                                             │
│ Current Price: 142.50 kr  [+1.2% today]   │
│ Your Position: 10 shares                   │
│ Position Value: 1,425 kr (0.32% of port)  │
│ Entry Price: 138 kr (average)              │
│                                             │
│ P&L: +45 kr (+3.2%) 📈                    │
│ 1M: +4.2%  | 3M: +12.5%  | YTD: +18.3%   │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│ Price Chart (Interactive)                  │
│                                             │
│ [1D] [5D] [1M] [3M] [1Y] [ALL]            │
│                                             │
│ [Line chart showing price history]        │
│                                             │
│ Hover: Show price on date                  │
│ Drag: Select date range                    │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│ Company Overview                           │
│                                             │
│ Description:                               │
│ Addtech is a leading technology solutions  │
│ provider in Northern Europe...             │
│                                             │
│ Metrics:                                   │
│ P/E: 18.2  |  P/B: 2.4  |  Div Yield: 2.1%│
│ ROE: 15.3% | ROIC: 12.8% | Debt/Equity: 0.4│
│                                             │
│ [Read Full Profile] [Visit Website]        │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│ Actions                                    │
│                                             │
│ [Set Price Alert]  [View Analyst Reports] │
│ [View Dividend Calendar] [Remove Position]│
└────────────────────────────────────────────┘
```

**Key Features**:
- Real-time price and P&L
- Interactive price chart
- Company fundamentals
- Why it's in portfolio (which strategy, scoring)
- News feed integration (optional)
- Alerts (price target, dividend payment)

---

### Strategies

**Purpose**: Understand each strategy, see rules, review historical performance  
**Primary users**: New users learning, strategy comparison

**Layout**:
```
┌────────────────────────────────────────────┐
│ Sammansatt Momentum                        │
│                                             │
│ How It Works:                              │
│ Selects the top 10 stocks by momentum      │
│ (3m, 6m, 12m average returns) filtered    │
│ by Piotroski F-Score quality gate.        │
│                                             │
│ Rebalancing: Quarterly (Mar, Jun, Sep, Dec)│
│ Holdings: 10 equal-weighted stocks        │
│ Est. Annual Return: ~15% (2001-2021)      │
│ Annual Cost: ~0.2% (quarterly rebalancing)│
│                                             │
│ [View Rules] [View Holdings] [Performance]│
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│ Strategy Selection (for custom portfolio)  │
│                                             │
│ ☑️ Sammansatt Momentum (15%)  [+][-]       │
│ ☑️ Trendande Värde (25%)      [+][-]       │
│ ☑️ Trendande Utdelning (20%)  [+][-]       │
│ ☑️ Trendande Kvalitet (40%)   [+][-]       │
│                                             │
│ Total: 100%                                │
│ Est. Annual Return: 12.1%  ← Blended      │
│                                             │
│ [Save as Custom Portfolio]                │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│ Performance Comparison (2001-2025)         │
│                                             │
│           Momentum  Värde  Utd.  Kvalitet  │
│ 1Y Ret.   +12.5%   +8.2%  +7.9%  +10.1%  │
│ 3Y Ret.   +35.2%   +18.3% +15.2% +28.1%  │
│ 5Y Ret.   +68.4%   +42.1% +38.9% +59.3%  │
│ YTD Ret.  +5.3%    +2.1%  +1.8%  +4.2%   │
│ Sharpe    1.35     1.18   1.05   1.28    │
│ MaxDD     -32%     -28%   -25%   -30%    │
│                                             │
│ [View Full Table] [Download CSV]          │
└────────────────────────────────────────────┘
```

**Key Features**:
- Strategy explanation (non-technical)
- Rules and logic (when rebalanced, how selected)
- Historical performance data
- Risk metrics (Sharpe, max drawdown)
- Component stocks
- Strategy comparison
- Custom portfolio builder

---

### Portfolio Analysis

**Purpose**: Understand portfolio composition, risk, sector exposure  
**Primary users**: Advanced users, portfolio optimization

**Layout**:
```
┌────────────────────────────────────────────┐
│ Asset Allocation                           │
│                                             │
│ By Strategy:                               │
│ Momentum: 38%    [████████          ]     │
│ Värde: 25%       [█████             ]     │
│ Utdelning: 20%   [████              ]     │
│ Kvalitet: 17%    [███               ]     │
│                                             │
│ By Sector:                                 │
│ Technology: 28%  [██████            ]     │
│ Industrials: 22% [████              ]     │
│ Financials: 18%  [███               ]     │
│ Consumer: 15%    [███               ]     │
│ Other: 17%       [███               ]     │
│                                             │
│ By Market Cap:                             │
│ Large Cap: 65%   [█████████████     ]     │
│ Mid Cap: 25%     [█████             ]     │
│ Small Cap: 10%   [██                ]     │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│ Risk Analysis                              │
│                                             │
│ Portfolio Volatility: 18.2%                │
│ Benchmark (OMX Stockholm): 16.5%           │
│ Beta: 1.05                                 │
│                                             │
│ Correlation Matrix:                        │
│       Momen  Värde  Utd.   Kvalit         │
│ Momen  1.0   0.62   0.58   0.71          │
│ Värde  0.62  1.0    0.78   0.85          │
│ Utd.   0.58  0.78   1.0    0.72          │
│ Kvalit 0.71  0.85   0.72   1.0           │
│                                             │
│ Diversification Score: 7/10 (Good)        │
│                                             │
│ [View Stress Test] [Scenario Analysis]    │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│ Concentration Risk                         │
│                                             │
│ Top 10 Holdings (Herfindahl Index)         │
│ 1. ADD    3.2%  ████                      │
│ 2. SAAB   2.8%  ███                       │
│ 3. VOLVA  2.5%  ███                       │
│ ...                                        │
│ 10. XYZ   1.8%  ██                        │
│                                             │
│ Concentration: 24.3% (Moderate)           │
│ Recommendation: Well-diversified ✓        │
└────────────────────────────────────────────┘
```

**Key Features**:
- Strategy allocation (pie chart)
- Sector exposure (heatmap or pie)
- Market cap breakdown
- Volatility and correlation
- Concentration metrics
- Stress testing (what if market drops 20%?)

---

### Alerts & Notifications

**Purpose**: Keep user informed of portfolio events, strategy changes, price movements  
**Primary users**: All users (background notifications)

**Layout**:
```
┌────────────────────────────────────────────┐
│ Notification Center                        │
│                                             │
│ ⚙️ Settings                                │
│                                             │
│ Recent:                                    │
│                                             │
│ 📈 Momentum added: ABC (Nov 5)            │
│    "ABC qualified for top 10 momentum     │
│    stocks this quarter."                  │
│    [View Strategy] [Dismiss]              │
│                                             │
│ 💰 Dividend Upcoming: ADD (Nov 8)         │
│    "ADD will pay dividend of 3.50 kr/sh  │
│    on Nov 15. Ex-date: Nov 8"            │
│    [View Dates] [Dismiss]                │
│                                             │
│ 🔔 Price Alert: SAAB (Nov 3)             │
│    "SAAB reached your target price of    │
│    185 kr. Current: 186 kr"              │
│    [Set New Alert] [Dismiss]             │
│                                             │
│ ⏱️ Rebalancing Reminder (Oct 25)          │
│    "Quarterly rebalancing in 5 days.     │
│    Review changes: 4 SELL, 3 BUY"        │
│    [Review Changes] [Dismiss]            │
│                                             │
│ [View All] [Clear All]                   │
└────────────────────────────────────────────┘
```

**Alert Types**:
- Strategy changes (stock added/removed)
- Dividend announcements
- Price targets reached
- Rebalancing reminders
- Portfolio milestones (reached 50k kr, etc.)
- System updates

**Notification Settings** (in Settings page):
- Email notifications: Enable/disable
- In-app notifications: Real-time, daily digest, weekly digest
- Push notifications: Mobile only
- Alert types: Which alerts to receive
- Quiet hours: Don't notify between 22:00-08:00

---

### Settings & Preferences

**Purpose**: Customize app behavior, manage data, adjust display  
**Primary users**: All users (occasionally)

**Layout**:
```
┌────────────────────────────────────────────┐
│ Settings                                   │
│                                             │
│ Account & Security                        │
│ • Email: user@example.com   [Change]      │
│ • Password                  [Change]      │
│ • Two-Factor Auth           [Enable]      │
│ • Active Sessions           [Manage]      │
│                                             │
│ Display & Preferences                     │
│ ◉ Dark Mode   ○ Light Mode                │
│ Currency:     [SEK dropdown]              │
│ Number Format: [1,234.56]   [1 234,56]   │
│ Chart Style:  [Candlestick] [Line]       │
│                                             │
│ Notifications                             │
│ ☑️ Email Notifications      [Settings]   │
│ ☑️ Push Notifications       [Settings]   │
│ ☑️ Rebalancing Reminders    [ON] [OFF]   │
│ ☑️ Dividend Alerts          [ON] [OFF]   │
│                                             │
│ Portfolio Settings                        │
│ Initial Investment: 450,000 kr            │
│ Target Allocation: [Custom] [4-Strategy] │
│ Rebalancing Frequency: [Quarterly]       │
│                                             │
│ Data & Export                             │
│ • Download CSV Export       [Export]     │
│ • Download PDF Report       [Export]     │
│ • Delete All Data           [Confirm]    │
│                                             │
│ About                                     │
│ • Version: 1.2.5                          │
│ • Privacy Policy  • Terms of Service     │
│ • Contact Support [Email]                │
└────────────────────────────────────────────┘
```

**Key Features**:
- Account management
- Display preferences (dark/light, currency)
- Notification controls
- Portfolio configuration
- Data export
- Privacy and compliance

---

### Generic Page Template

**For any unknown/future pages not specified above**

**Purpose**: Maintain UI consistency across all pages  
**Usage**: Apply this structure to any new page not explicitly designed

**Layout**:
```
┌────────────────────────────────────────────┐
│ [Page Title] / [Breadcrumb]  [Context Menu]│
├────────────────────────────────────────────┤
│                                             │
│ [Primary Content Area]                    │
│                                             │
│ Main section with consistent:              │
│ • Padding: 24px (md) minimum              │
│ • Card backgrounds: #1a1f2e               │
│ • Borders: 1px #2d3748                   │
│ • Typography: Use type scale above        │
│ • Colors: Follow semantic color system    │
│ • Spacing: 8px grid multiples             │
│ • Components: Use Chakra/shadcn UI        │
│                                             │
│ [Action Buttons]                          │
│                                             │
│ • Primary actions (right-aligned)         │
│ • Secondary actions (left or inline)      │
│ • Destructive actions (danger red)        │
│                                             │
└────────────────────────────────────────────┘

Responsive Behavior:
- Desktop: Full-width content, side padding 32px
- Tablet: Full-width, side padding 16px
- Mobile: Full-width, side padding 16px, stacked layout
```

**Template Components** (use for consistency):
- Header: Page title, optional subtitle, optional breadcrumbs
- Actions bar: Primary/secondary buttons, filters
- Main content: Cards, tables, charts, forms
- Sidebar (optional): Filters, related links, metadata
- Footer (optional): Pagination, additional actions

**Template CSS** (use for all pages):
```css
.page-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: var(--space-xl) var(--space-lg);
}

.page-header {
  margin-bottom: var(--space-xl);
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--space-lg);
}

.page-content {
  display: flex;
  gap: var(--space-lg);
  margin-bottom: var(--space-xl);
}

.content-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.content-sidebar {
  width: 240px;
}

@media (max-width: 768px) {
  .page-content {
    flex-direction: column;
  }
  
  .content-sidebar {
    width: 100%;
  }
}
```

---

## Interactive Behaviors & Micro-Interactions

### Hover & Click States

**Card Hover**:
```javascript
Transition: 200ms cubic-bezier(0.16, 1, 0.3, 1)
box-shadow: 0 1px 3px → 0 10px 25px
transform: translateY(0) → translateY(-4px)
cursor: pointer (if clickable)
```

**Button Click**:
```javascript
On click:
  opacity: 1 → 0.9 (brief visual feedback)
  transform: scale(0.98) (press effect)
  duration: 100ms
On release:
  Return to normal state smoothly (100ms)
```

**Input Focus**:
```javascript
border-color: #2d3748 → #00b4d8
box-shadow: none → 0 0 0 3px rgba(0,180,216,0.1)
transition: 150ms
```

**Number Animation** (for price changes):
```javascript
Color change: Current color → Green/Red
Fade out: After 2 seconds
Duration: 300ms color change + 1000ms hold + 500ms fade
```

### Loading & Empty States

**Skeleton Loading**:
- Show placeholder matching final layout
- Use shimmer animation (see CSS above)
- Don't use spinners
- Prevents layout shift (maintains dimensions)

**Empty State**:
- Show helpful illustration
- Clear message ("No holdings yet" not just empty)
- Primary action: "Add Holdings" or "Import Data"
- Secondary: Link to help/tutorial

**Error State**:
- Red border on problematic input
- Error message below (red text, 12px)
- Helpful suggestion (not just "Error!")
- Recover button (retry/dismiss)

### Real-Time Updates

**Portfolio Value Counter**:
```javascript
// Smooth animation of numbers
animate from: previousValue
to: currentValue
duration: 500ms
easing: easeInOutQuad
format: With appropriate decimals (kr, %)
```

**Price Ticker**:
```javascript
// Up/down arrow + color
Show: ▲ +1.2% (green) or ▼ -0.8% (red)
Animate: Brief color flash (0.5s)
Update: Every 15 seconds (or real-time if available)
```

---

## Mobile Responsiveness

### Breakpoints & Layout Shifts

| Breakpoint | Width | Device | Layout |
|-----------|-------|--------|--------|
| **xs** | 320px | Small phone | Single column, full-width |
| **sm** | 640px | Phone landscape | Single column, padded |
| **md** | 768px | Tablet | Single/two column |
| **lg** | 1024px | Desktop | Full layout |
| **xl** | 1280px | Wide desktop | Max-width container |

### Mobile-First CSS Pattern
```css
/* Mobile first (base styles) */
.component {
  display: block;
  width: 100%;
  padding: 16px;
}

/* Then enhance for larger screens */
@media (min-width: 768px) {
  .component {
    display: flex;
    width: 50%;
    padding: 24px;
  }
}
```

### Mobile Navigation

**Top Navigation Bar** (56px height):
- Logo/home link (left)
- Page title (center)
- Menu button (right, hamburger icon)

**Hamburger Menu** (Slide from left):
- Full-screen drawer
- Navigation links (vertical)
- Settings link
- Close button (X, top-right)

**Bottom Tab Bar** (56px height):
- 5 main sections (swipeable):
  1. Portfolio (home icon)
  2. Strategies (chart icon)
  3. Rebalancing (calendar icon)
  4. Alerts (bell icon)
  5. Settings (gear icon)

### Touch Targets
- Minimum: 48x48px (WCAG AA standard)
- Spacing: At least 8px between targets
- Large buttons: 56-64px height
- All interactive elements: Keyboard accessible (tab order)

### Orientation Changes
- No full-page reload
- Smooth transition of layout
- Preserve scroll position when possible
- Adjust modal/drawer sizes

---

## Tech Stack Recommendations

### Frontend Framework
- **React 18+** with TypeScript
- **Next.js 14+** (optional, for SSR/SSG)

### Component Library
**Primary: Chakra UI**
```bash
npm install @chakra-ui/react @emotion/react @emotion/styled framer-motion
```

Features:
- Accessible by default
- Dark mode built-in
- Responsive design utilities
- Customizable theme
- 50+ pre-built components

**Example**:
```tsx
import { Box, Button, Card, Text, VStack } from '@chakra-ui/react';

export function Dashboard() {
  return (
    <Card bg="gray.900" borderColor="gray.700">
      <VStack spacing="md">
        <Text fontSize="3xl" fontWeight="600" color="cyan.400">
          $450,230
        </Text>
        <Button colorScheme="cyan" width="100%">
          View Holdings
        </Button>
      </VStack>
    </Card>
  );
}
```

### Charts & Visualization
- **Recharts** (recommended for fintech)
  - React-native, responsive
  - Interactive tooltips
  - 20+ chart types
  
```bash
npm install recharts
```

### Tables
- **TanStack Table** (React Table v8)
  - Headless, highly customizable
  - Sorting, filtering, pagination
  - Column visibility toggle
  
```bash
npm install @tanstack/react-table
```

### Icons
- **Lucide React** (modern, consistent)
```bash
npm install lucide-react
```

### State Management
- **TanStack Query** (server state)
  ```bash
  npm install @tanstack/react-query
  ```
  
- **Zustand** (client state)
  ```bash
  npm install zustand
  ```

### Styling
- **Tailwind CSS** (utility-first)
  ```bash
  npm install -D tailwindcss postcss autoprefixer
  ```

- **Framer Motion** (animations)
  ```bash
  npm install framer-motion
  ```

### Real-Time Updates
- **Socket.io** (live prices)
  ```bash
  npm install socket.io-client
  ```

- **SWR** (data fetching + caching)
  ```bash
  npm install swr
  ```

---

## Accessibility & Performance

### Accessibility (WCAG 2.1 AA)

**Color Contrast**:
- Minimum 4.5:1 for normal text
- 3:1 for large text (18px+)
- Test with: https://webaim.org/resources/contrastchecker/

**Keyboard Navigation**:
- Tab order: Logical (left-to-right, top-to-bottom)
- Focus visible: 2px border on all interactive elements
- Escape key: Close modals/drawers
- Enter/Space: Activate buttons

**Screen Readers**:
- Semantic HTML (`<button>` not `<div role="button">`)
- ARIA labels for unlabeled icons
- Form labels associated with inputs
- Skip links for navigation

**Text & Fonts**:
- No text smaller than 12px (except metadata)
- Line spacing ≥ 1.5x
- Font weight ≥ 400 (no super-thin fonts)
- Avoid all-caps for body text

### Performance

**Page Load**:
- Target: <2s on 4G mobile
- Use code splitting for pages
- Lazy load charts/tables below fold
- Compress images (WebP format)

**Interaction Response**:
- Target: <100ms for all clicks
- Use skeleton screens (not spinners)
- Optimize re-renders (useMemo, useCallback)
- Debounce search/filter inputs (300ms)

**Bundle Size**:
- Target: <200KB (gzipped)
- Monitor with: `npm run build --analyze`
- Use dynamic imports for large libraries

**Monitoring**:
- Use Sentry for error tracking
- Use Google Analytics for user behavior
- Monitor Core Web Vitals (LCP, FID, CLS)

---

## Design Files & Reference

### Inspiration (Visual Style)
- **Robinhood**: Clean data visualization, mobile-first
- **M1 Finance**: Interactive, gamified portfolio visualization
- **Betterment**: Minimalist design, focus on education
- **TradingView**: Professional chart-heavy interface
- **Morningstar**: Data visualization expert

### Figma Components (When Creating)
- Button (all variants: primary, secondary, danger, sizes)
- Card (with shadow states)
- Input (all states: empty, focused, filled, error)
- Modal (with backdrop and animations)
- Toggle/Switch
- Chart container (responsive wrapper)
- Navigation components (top bar, bottom tab, sidebar)

---

## Glossary of Terms Used in This Brief

| Term | Definition | Example |
|------|-----------|---------|
| **Skeleton Screen** | Placeholder layout matching final content | Gray boxes before content loads |
| **Micro-interaction** | Small animation/feedback on user action | Button darkens on hover |
| **Utility-first CSS** | Classes for single properties | `flex`, `p-4`, `text-sm` |
| **Dark mode** | High contrast, dark backgrounds | #0f1419 background |
| **CLS** | Cumulative Layout Shift (performance metric) | Layout shouldn't jump during load |
| **WCAG** | Web Content Accessibility Guidelines | Standard for accessibility |
| **ARIA** | Accessible Rich Internet Applications | Attributes for screen readers |
| **Semantic HTML** | Meaningful elements (`<button>` not `<div>`) | Improves accessibility |

---

## Version History

- **v1.0** (Dec 30, 2025): Initial design brief created
  - Core design system
  - 7 main page templates
  - Generic template for unknown pages
  - Tech stack recommendations
  - Accessibility & performance standards

---

## Questions?

For clarifications on design choices:
1. Review the principle that motivated it (top of relevant section)
2. Check the 2025 fintech design trends section
3. Refer to reference apps (Robinhood, Betterment, etc.)
4. Test with real users—data beats theory
