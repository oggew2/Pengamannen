import { createSystem, defaultConfig, defineConfig } from '@chakra-ui/react';

const config = defineConfig({
  globalCss: {
    'html, body': {
      bg: 'bg',
      color: 'fg',
    },
  },
  theme: {
    tokens: {
      colors: {
        brand: {
          50: { value: '#e6f7ff' },
          100: { value: '#b3e9ff' },
          200: { value: '#80dbff' },
          300: { value: '#4dcdff' },
          400: { value: '#1abfff' },
          500: { value: '#00b4d8' },
          600: { value: '#00a3c0' },
          700: { value: '#0090ad' },
          800: { value: '#007a94' },
          900: { value: '#00647a' },
          950: { value: '#004d5c' },
        },
        gray: {
          50: { value: '#f5f5f5' },
          100: { value: '#d1d5db' },
          200: { value: '#9ca3af' },
          300: { value: '#6b7280' },
          400: { value: '#4b5563' },
          500: { value: '#374151' },
          600: { value: '#2d3748' },
          700: { value: '#1a1f2e' },
          800: { value: '#0f1419' },
          900: { value: '#0a0e13' },
          950: { value: '#050709' },
        },
      },
      fonts: {
        heading: { value: '"Geist", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' },
        body: { value: '"Geist", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' },
        mono: { value: '"JetBrains Mono", "Fira Code", "Courier New", monospace' },
      },
    },
    semanticTokens: {
      colors: {
        // Background tokens
        bg: { value: '{colors.gray.800}' },
        'bg.subtle': { value: '{colors.gray.700}' },
        'bg.muted': { value: '{colors.gray.600}' },
        'bg.emphasized': { value: '{colors.gray.500}' },
        
        // Foreground/text tokens
        fg: { value: '{colors.gray.100}' },
        'fg.muted': { value: '{colors.gray.200}' },
        'fg.subtle': { value: '{colors.gray.300}' },
        
        // Border tokens
        border: { value: '{colors.gray.600}' },
        'border.muted': { value: '{colors.gray.500}' },
        'border.subtle': { value: '{colors.gray.400}' },
        
        // Brand color palette
        brand: {
          solid: { value: '{colors.brand.500}' },
          contrast: { value: 'white' },
          fg: { value: '{colors.brand.500}' },
          muted: { value: '{colors.brand.100}' },
          subtle: { value: '{colors.brand.200}' },
          emphasized: { value: '{colors.brand.600}' },
          focusRing: { value: '{colors.brand.500}' },
        },
        
        // Semantic status colors
        success: {
          solid: { value: '#10b981' },
          fg: { value: '#10b981' },
          muted: { value: 'rgba(16, 185, 129, 0.2)' },
          subtle: { value: 'rgba(16, 185, 129, 0.15)' },
        },
        error: {
          solid: { value: '#ef4444' },
          fg: { value: '#ef4444' },
          muted: { value: 'rgba(239, 68, 68, 0.2)' },
          subtle: { value: 'rgba(239, 68, 68, 0.15)' },
        },
        warning: {
          solid: { value: '#f59e0b' },
          fg: { value: '#f59e0b' },
          muted: { value: 'rgba(245, 158, 11, 0.2)' },
          subtle: { value: 'rgba(245, 158, 11, 0.15)' },
        },
        info: {
          solid: { value: '#3b82f6' },
          fg: { value: '#3b82f6' },
          muted: { value: 'rgba(59, 130, 246, 0.2)' },
          subtle: { value: 'rgba(59, 130, 246, 0.15)' },
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);
