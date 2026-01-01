/**
 * Format number as Swedish currency: 123 456 kr
 */
export function formatSEK(value: number | null | undefined, decimals = 0): string {
  if (value == null || isNaN(value)) return '—';
  return value.toLocaleString('sv-SE', { 
    minimumFractionDigits: decimals, 
    maximumFractionDigits: decimals 
  }) + ' kr';
}

/**
 * Format number with sign: +123 456 kr or -123 456 kr
 */
export function formatSEKWithSign(value: number | null | undefined, decimals = 0): string {
  if (value == null || isNaN(value)) return '—';
  const sign = value >= 0 ? '+' : '';
  return sign + formatSEK(value, decimals);
}

/**
 * Format percentage: 12,3%
 */
export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value == null || isNaN(value)) return '—';
  return value.toLocaleString('sv-SE', { 
    minimumFractionDigits: decimals, 
    maximumFractionDigits: decimals 
  }) + '%';
}
