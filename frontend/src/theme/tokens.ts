// Design tokens matching CSS variables in index.css
export const tokens = {
  colors: {
    bg: {
      primary: '#0f1419',
      secondary: '#1a1f2e',
      hover: '#2d3748',
      active: '#404d64',
    },
    text: {
      primary: '#f5f5f5',
      secondary: '#d1d5db',
      muted: '#9ca3af',
      disabled: '#4b5563',
    },
    brand: {
      primary: '#00b4d8',
      hover: '#00a3c0',
      active: '#0090ad',
    },
    semantic: {
      success: '#10b981',
      successLight: 'rgba(16, 185, 129, 0.2)',
      error: '#ef4444',
      errorLight: 'rgba(239, 68, 68, 0.2)',
      warning: '#f59e0b',
      warningLight: 'rgba(245, 158, 11, 0.2)',
      info: '#3b82f6',
      infoLight: 'rgba(59, 130, 246, 0.2)',
    },
    border: {
      default: '#2d3748',
      hover: '#404d64',
      focus: '#00b4d8',
    },
  },
  fonts: {
    heading: '"Geist", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    body: '"Geist", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    mono: '"JetBrains Mono", "Fira Code", "Courier New", monospace',
  },
  fontSizes: {
    xs: '12px',
    sm: '14px',
    md: '16px',
    lg: '18px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '32px',
  },
  fontWeights: {
    normal: 400,
    medium: 500,
    semibold: 600,
  },
  lineHeights: {
    tight: 1.2,
    snug: 1.3,
    normal: 1.4,
    relaxed: 1.5,
    loose: 1.6,
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
  },
  radii: {
    sm: '4px',
    md: '6px',
    lg: '8px',
    xl: '12px',
  },
  shadows: {
    sm: '0 1px 3px rgba(0,0,0,0.1)',
    md: '0 4px 12px rgba(0,0,0,0.15)',
    lg: '0 10px 25px rgba(0,0,0,0.2)',
  },
  transitions: {
    fast: '150ms cubic-bezier(0.16, 1, 0.3, 1)',
    normal: '200ms cubic-bezier(0.16, 1, 0.3, 1)',
  },
  sizes: {
    sidebar: '240px',
    header: '56px',
    contentMax: '1000px',
  },
} as const;
