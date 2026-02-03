import { useState, useCallback } from 'react';
import { Box, Text, Button, VStack, HStack, Input, Badge, Spinner } from '@chakra-ui/react';
import { useCelebration } from './FintechEffects';

interface Transaction {
  date: string;
  ticker: string | null;
  name: string;
  isin: string;
  type: 'BUY' | 'SELL';
  shares: number;
  price_local: number;
  price_sek: number;
  currency: string;
  fee: number;
  hash: string;
}

interface Position {
  ticker: string;
  shares: number;
  avg_price_local: number;
  avg_price_sek: number;
  total_cost: number;
  fees: number;
  currency: string;
  fx_rate: number;
  warning?: string;
}

interface ImportPreview {
  parsed: number;
  new: number;
  duplicates_skipped: number;
  matched: number;
  unmatched: Array<{ name: string; isin: string; date: string }>;
  positions: Position[];
  summary: {
    total_fees: number;
    total_invested: number;
    unique_stocks: number;
    date_range: { start: string; end: string } | null;
  };
  transactions: Transaction[];
}

type ImportMode = 'add_new' | 'replace';

export function CsvImporter({ onImportComplete, onSyncComplete }: { 
  onImportComplete?: () => void;
  onSyncComplete?: (holdings: Array<{ticker: string; shares: number; buyPrice: number}>) => void;
}) {
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mode, setMode] = useState<ImportMode>('add_new');
  const [importResult, setImportResult] = useState<{ imported: number } | null>(null);
  const [syncing, setSyncing] = useState(false);
  const { celebrate } = useCelebration();

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const processFile = async (file: File) => {
    setLoading(true);
    setError(null);
    setPreview(null);
    setImportResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/v1/portfolio/import-csv', {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail) || 'Import failed');
      }

      const data: ImportPreview = await res.json();
      setPreview(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg === '[object Object]' ? 'Import failed - check file format' : msg);
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files?.[0]) {
      processFile(files[0]);
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files?.[0]) {
      processFile(files[0]);
    }
  };

  const confirmImport = async () => {
    if (!preview) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/v1/portfolio/import-confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          transactions: preview.transactions,
          mode,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Import failed');
      }

      const data = await res.json();
      setImportResult(data);
      celebrate('first_import'); // Trigger celebration on successful import
      onImportComplete?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save transactions');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setPreview(null);
    setImportResult(null);
    setError(null);
  };

  const syncToPortfolio = async () => {
    setSyncing(true);
    setError(null);
    try {
      const res = await fetch('/v1/portfolio/sync-to-holdings', {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Sync failed');
      }
      const data = await res.json();
      if (data.warning) {
        setError(data.warning);  // Show warning but still proceed
      }
      onSyncComplete?.(data.holdings);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to sync');
    } finally {
      setSyncing(false);
    }
  };

  // Success state
  if (importResult) {
    return (
      <Box p={6} bg="green.900" borderRadius="lg">
        <VStack gap={4}>
          <Text fontSize="xl" fontWeight="bold" color="green.200">✓ Import klar!</Text>
          <Text color="gray.300">
            {importResult.imported} transaktioner importerade
          </Text>
          <HStack gap={2}>
            <Button onClick={reset} colorScheme="green" variant="outline">
              Importera fler
            </Button>
            <Button 
              onClick={syncToPortfolio} 
              colorScheme="blue"
              loading={syncing}
            >
              Synka till portfölj
            </Button>
          </HStack>
          {error && <Text color="orange.300" fontSize="sm">{error}</Text>}
        </VStack>
      </Box>
    );
  }

  // Preview state
  if (preview) {
    return (
      <Box p={4} bg="gray.800" borderRadius="lg">
        <VStack gap={4} align="stretch">
          <HStack justify="space-between">
            <Text fontSize="lg" fontWeight="bold">
              Hittade {preview.parsed} transaktioner
            </Text>
            <Button size="sm" variant="ghost" onClick={reset}>✕</Button>
          </HStack>

          {preview.summary.date_range && (
            <Text color="gray.400" fontSize="sm">
              {preview.summary.date_range.start} → {preview.summary.date_range.end}
            </Text>
          )}

          {/* Stats */}
          <HStack gap={4} flexWrap="wrap">
            <Badge colorScheme="green">{preview.matched} matchade</Badge>
            {preview.duplicates_skipped > 0 && (
              <Badge colorScheme="yellow">{preview.duplicates_skipped} duplicerade</Badge>
            )}
            {preview.unmatched.length > 0 && (
              <Badge colorScheme="red">{preview.unmatched.length} ej matchade</Badge>
            )}
          </HStack>

          {/* Import mode */}
          <Box>
            <Text fontWeight="medium" mb={2}>Importläge:</Text>
            <HStack gap={2}>
              <Button
                size="sm"
                variant={mode === 'add_new' ? 'solid' : 'outline'}
                colorScheme={mode === 'add_new' ? 'blue' : 'gray'}
                onClick={() => setMode('add_new')}
              >
                ➕ Lägg till nya
              </Button>
              <Button
                size="sm"
                variant={mode === 'replace' ? 'solid' : 'outline'}
                colorScheme={mode === 'replace' ? 'orange' : 'gray'}
                onClick={() => setMode('replace')}
              >
                🔄 Ersätt allt
              </Button>
            </HStack>
          </Box>

          {/* Positions preview */}
          {preview.positions.length > 0 && (
            <Box>
              <Text fontWeight="medium" mb={2}>Beräknade positioner:</Text>
              <Box maxH="200px" overflowY="auto" bg="gray.900" borderRadius="md" p={2}>
                {preview.positions.map((pos) => (
                  <HStack key={pos.ticker} justify="space-between" py={1} borderBottom="1px" borderColor="gray.700">
                    <HStack>
                      <Text fontWeight="medium">{pos.ticker}</Text>
                      {pos.warning && <Badge colorScheme="red" size="sm">⚠️</Badge>}
                    </HStack>
                    <HStack gap={4}>
                      <Text color="gray.400">{pos.shares} st</Text>
                      <Text color="gray.400">
                        @ {pos.avg_price_local.toFixed(2)} {pos.currency}
                        {pos.currency !== 'SEK' && <Text as="span" color="gray.500"> ≈ {pos.avg_price_sek.toFixed(0)} kr</Text>}
                      </Text>
                      <Text fontWeight="medium">{Math.round(pos.total_cost).toLocaleString('sv-SE')} kr</Text>
                    </HStack>
                  </HStack>
                ))}
              </Box>
            </Box>
          )}

          {/* Unmatched warning */}
          {preview.unmatched.length > 0 && (
            <Box bg="red.900" p={3} borderRadius="md">
              <Text fontWeight="medium" color="red.200" mb={2}>
                ⚠️ Kunde inte matcha {preview.unmatched.length} transaktioner:
              </Text>
              {preview.unmatched.slice(0, 5).map((u, i) => (
                <Text key={i} fontSize="sm" color="gray.300">
                  {u.name} ({u.isin})
                </Text>
              ))}
            </Box>
          )}

          {/* Summary */}
          <HStack justify="space-between" bg="gray.900" p={3} borderRadius="md">
            <VStack align="start" gap={0}>
              <Text color="gray.400" fontSize="sm">Totalt investerat</Text>
              <Text fontWeight="bold">{Math.round(preview.summary.total_invested).toLocaleString('sv-SE')} kr</Text>
            </VStack>
            <VStack align="start" gap={0}>
              <Text color="gray.400" fontSize="sm">Avgifter</Text>
              <Text fontWeight="bold">{Math.round(preview.summary.total_fees).toLocaleString('sv-SE')} kr</Text>
            </VStack>
            <VStack align="start" gap={0}>
              <Text color="gray.400" fontSize="sm">Aktier</Text>
              <Text fontWeight="bold">{preview.summary.unique_stocks}</Text>
            </VStack>
          </HStack>

          {error && <Text color="red.400">{error}</Text>}

          {/* All duplicates warning */}
          {preview.new === 0 && preview.duplicates_skipped > 0 && (
            <Box bg="yellow.900" p={3} borderRadius="md">
              <Text color="yellow.200" fontSize="sm">
                ⚠️ Alla {preview.duplicates_skipped} transaktioner finns redan. Välj "Ersätt allt" för att importera på nytt.
              </Text>
            </Box>
          )}

          {/* Actions */}
          <HStack justify="flex-end" gap={2}>
            <Button variant="ghost" onClick={reset}>Avbryt</Button>
            <Button
              colorScheme="blue"
              onClick={confirmImport}
              loading={loading}
              disabled={preview.new === 0 && mode === 'add_new'}
            >
              {mode === 'replace' ? `Ersätt med ${preview.parsed}` : `Importera ${preview.new}`} transaktioner
            </Button>
          </HStack>
        </VStack>
      </Box>
    );
  }

  // Upload state
  return (
    <Box p={4}>
      <VStack gap={4}>
        <Box
          w="100%"
          p={8}
          border="2px dashed"
          borderColor={dragActive ? 'blue.400' : 'gray.600'}
          borderRadius="lg"
          bg={dragActive ? 'blue.900' : 'gray.800'}
          textAlign="center"
          cursor="pointer"
          transition="all 0.2s"
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => document.getElementById('csv-input')?.click()}
          role="button"
          tabIndex={0}
          aria-label="Ladda upp CSV-fil genom att dra och släppa eller klicka"
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              document.getElementById('csv-input')?.click();
            }
          }}
        >
          <Input
            id="csv-input"
            type="file"
            accept=".csv"
            display="none"
            onChange={handleFileSelect}
            aria-label="Välj CSV-fil"
          />
          
          {loading ? (
            <VStack>
              <Spinner size="lg" color="blue.400" aria-label="Laddar" />
              <Text color="gray.400">Läser in...</Text>
            </VStack>
          ) : (
            <VStack>
              <Text fontSize="3xl" aria-hidden="true">📥</Text>
              <Text fontWeight="medium">Dra och släpp CSV-fil här</Text>
              <Text color="gray.400" fontSize="sm">eller klicka för att välja</Text>
              <Text color="gray.500" fontSize="xs" mt={2}>Accepterar: .csv (max 10 MB)</Text>
            </VStack>
          )}
        </Box>

        {error && (
          <Box 
            p={3} 
            bg="red.900" 
            borderRadius="md" 
            w="100%"
            role="alert"
            aria-live="polite"
          >
            <Text color="red.200">{error}</Text>
          </Box>
        )}

        <Box bg="gray.800" p={3} borderRadius="md" w="100%">
          <Text fontSize="sm" color="gray.400">
            💡 Exportera från Avanza: Mina sidor → Transaktioner → Exportera
          </Text>
        </Box>
      </VStack>
    </Box>
  );
}
