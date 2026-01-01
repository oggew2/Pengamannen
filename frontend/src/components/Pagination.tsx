import { HStack, Button, Text } from '@chakra-ui/react';

interface Props {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, totalPages, onPageChange }: Props) {
  if (totalPages <= 1) return null;
  
  return (
    <HStack gap="8px" justify="center" mt="16px">
      <Button size="sm" variant="ghost" onClick={() => onPageChange(page - 1)} disabled={page === 1}>
        ←
      </Button>
      <Text fontSize="sm" color="gray.300">
        {page} / {totalPages}
      </Text>
      <Button size="sm" variant="ghost" onClick={() => onPageChange(page + 1)} disabled={page === totalPages}>
        →
      </Button>
    </HStack>
  );
}
