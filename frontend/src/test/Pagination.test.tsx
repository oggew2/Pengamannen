import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { Pagination } from '../components/Pagination';

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <ChakraProvider value={defaultSystem}>{children}</ChakraProvider>
);

describe('Pagination', () => {
  it('renders nothing when totalPages <= 1', () => {
    const { container } = render(
      <Pagination page={1} totalPages={1} onPageChange={() => {}} />,
      { wrapper }
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders page info correctly', () => {
    const { getByText } = render(
      <Pagination page={2} totalPages={5} onPageChange={() => {}} />,
      { wrapper }
    );
    expect(getByText('2 / 5')).toBeInTheDocument();
  });

  it('matches snapshot', () => {
    const { container } = render(
      <Pagination page={1} totalPages={3} onPageChange={() => {}} />,
      { wrapper }
    );
    expect(container).toMatchSnapshot();
  });
});
