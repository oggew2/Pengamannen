import { useState } from 'react';
import { Box, Text, VStack, HStack, Flex } from '@chakra-ui/react';

const CONTENT = {
  strategies: {
    title: 'Börslabbet Strategies',
    sections: [
      { title: 'Sammansatt Momentum', content: `The momentum strategy selects stocks with the strongest price trends over 3, 6, and 12 months. It uses the Piotroski F-Score as a quality filter to avoid "falling knives" - stocks that are cheap for good reasons.

**How it works:**
1. Calculate average return over 3M, 6M, and 12M periods
2. Filter out stocks with F-Score ≤ 3 (poor quality)
3. Select top 10 stocks by momentum score
4. Rebalance quarterly (March, June, September, December)

**Why it works:** Momentum is one of the most robust factors in academic finance. Stocks that have performed well tend to continue performing well in the short term.` },
      { title: 'Trendande Värde', content: `Combines value investing with momentum to avoid "value traps" - cheap stocks that stay cheap.

**6 Value Metrics:**
• P/E (Price/Earnings) - lower is better
• P/B (Price/Book) - lower is better  
• P/S (Price/Sales) - lower is better
• P/FCF (Price/Free Cash Flow) - lower is better
• EV/EBITDA - lower is better
• Dividend Yield - higher is better

**Process:**
1. Rank all stocks by composite value score
2. Keep top 10% most undervalued
3. From those, select top 10 by momentum
4. Rebalance annually in March` },
      { title: 'Trendande Utdelning', content: `Focuses on high dividend yield stocks with positive momentum to generate income while avoiding dividend cuts.

**Process:**
1. Rank stocks by dividend yield
2. Keep top 10% highest yielders
3. Select top 10 by momentum (avoids declining companies)
4. Rebalance annually in March

**Why momentum matters:** High yield alone can be a trap - companies often have high yields because their stock price has crashed. Adding momentum ensures you're buying companies with stable or rising prices.` },
      { title: 'Trendande Kvalitet', content: `Selects high-quality companies using profitability metrics, then filters by momentum.

**4 Quality Metrics (Sammansatt ROI):**
• ROE (Return on Equity)
• ROA (Return on Assets)
• ROIC (Return on Invested Capital)
• FCFROE (Free Cash Flow / Equity) - the "secret sauce"

**Process:**
1. Rank stocks by composite quality score
2. Keep top 10% highest quality
3. Select top 10 by momentum
4. Rebalance annually in March

**Why FCFROE:** Unlike accounting earnings, free cash flow is hard to manipulate. Companies generating real cash relative to equity are genuinely profitable.` }
    ]
  },
  fscore: {
    title: 'Piotroski F-Score',
    sections: [
      { title: 'What is F-Score?', content: `The Piotroski F-Score is a 0-9 scale measuring a company's financial strength. Developed by Stanford professor Joseph Piotroski in 2000, it identifies financially healthy companies among cheap stocks.

**Score Interpretation:**
• 8-9: Strong financial health
• 5-7: Average
• 0-4: Weak, potential distress` },
      { title: 'The 9 Criteria', content: `**Profitability (4 points):**
1. Positive ROA (net income / assets > 0)
2. Positive operating cash flow
3. ROA improving vs last year
4. Cash flow > net income (quality of earnings)

**Leverage & Liquidity (3 points):**
5. Long-term debt ratio decreasing
6. Current ratio improving
7. No new share dilution

**Operating Efficiency (2 points):**
8. Gross margin improving
9. Asset turnover improving

Each criterion scores 1 point if met, 0 if not.` },
      { title: 'How Börslabbet Uses It', content: `In the Sammansatt Momentum strategy, F-Score acts as a quality gate:

• Stocks with F-Score ≤ 3 are excluded
• This removes ~20% of stocks with weak financials
• Prevents buying "falling knives" - stocks crashing for fundamental reasons

**Research shows:** Combining momentum with quality filters significantly improves risk-adjusted returns.` }
    ]
  },
  isk: {
    title: 'ISK (Investeringssparkonto)',
    sections: [
      { title: 'What is ISK?', content: `ISK (Investment Savings Account) is a Swedish tax-advantaged account for stocks and funds. Instead of paying capital gains tax on profits, you pay a small annual tax based on account value.

**2024 Tax Rate:** ~0.9% of average account value
(Calculated as: Government borrowing rate + 1% × 30%)` },
      { title: 'ISK vs Regular Account', content: `**ISK Advantages:**
• No tax on dividends or capital gains
• No need to report individual trades
• Simple flat tax regardless of returns

**When ISK is better:**
• Expected returns > ~3% annually
• Active trading (no tax on each sale)
• Dividend stocks (dividends tax-free)

**When regular account might be better:**
• Very low expected returns
• Want to deduct losses against other income` },
      { title: 'ISK for Börslabbet Strategies', content: `ISK is ideal for Börslabbet strategies because:

1. **Quarterly rebalancing** - No capital gains tax on sales
2. **Dividend strategies** - Dividends received tax-free
3. **High expected returns** - Strategies target 10-15% annually

**Example:**
• 100,000 kr portfolio, 15% return = 15,000 kr gain
• ISK tax: ~900 kr (0.9% of value)
• Regular account: 4,500 kr (30% of gain)

**Savings: 3,600 kr per year**` }
    ]
  }
};

export default function EducationPage() {
  const [activeTab, setActiveTab] = useState<'strategies' | 'fscore' | 'isk'>('strategies');
  const [expandedSection, setExpandedSection] = useState<number | null>(0);

  const content = CONTENT[activeTab];

  return (
    <VStack gap="24px" align="stretch">
      <Text fontSize="2xl" fontWeight="bold" color="gray.50">Learn</Text>

      {/* Tabs */}
      <HStack gap="8px" flexWrap="wrap">
        {[
          { key: 'strategies', label: 'Strategies' },
          { key: 'fscore', label: 'F-Score' },
          { key: 'isk', label: 'ISK Guide' },
        ].map(tab => (
          <Box
            key={tab.key}
            as="button"
            px="16px"
            py="8px"
            borderRadius="6px"
            bg={activeTab === tab.key ? 'brand.500' : 'gray.700'}
            color={activeTab === tab.key ? 'white' : 'gray.200'}
            fontWeight="medium"
            fontSize="sm"
            onClick={() => { setActiveTab(tab.key as typeof activeTab); setExpandedSection(0); }}
            _hover={{ bg: activeTab === tab.key ? 'brand.600' : 'gray.600' }}
            transition="all 150ms"
          >
            {tab.label}
          </Box>
        ))}
      </HStack>

      {/* Content */}
      <Box bg="gray.700" borderRadius="8px" p="24px">
        <Text fontSize="xl" fontWeight="semibold" color="gray.50" mb="16px">{content.title}</Text>
        
        <VStack align="stretch" gap="12px">
          {content.sections.map((section, i) => (
            <Box key={i} borderRadius="6px" overflow="hidden" border="1px solid" borderColor="gray.600">
              <Flex
                as="button"
                w="100%"
                p="12px 16px"
                justify="space-between"
                align="center"
                bg={expandedSection === i ? 'gray.600' : 'transparent'}
                onClick={() => setExpandedSection(expandedSection === i ? null : i)}
                _hover={{ bg: 'gray.600' }}
                transition="background 150ms"
              >
                <Text fontSize="sm" fontWeight="medium" color="gray.100">{section.title}</Text>
                <Text color="gray.400">{expandedSection === i ? '−' : '+'}</Text>
              </Flex>
              {expandedSection === i && (
                <Box p="16px" bg="gray.650" borderTop="1px solid" borderColor="gray.600">
                  <Text fontSize="sm" color="gray.200" whiteSpace="pre-wrap" lineHeight="1.7">
                    {section.content}
                  </Text>
                </Box>
              )}
            </Box>
          ))}
        </VStack>
      </Box>
    </VStack>
  );
}
