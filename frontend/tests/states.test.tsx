import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Empty, ErrorState, Risk } from '../src/components/ui/States';
import { money, number, percent } from '../src/lib/format';

describe('Missing data and error presentation', () => {
  it('distinguishes missing values from zero', () => {
    expect(number(null)).toBe('Not available');
    expect(percent(undefined)).toBe('Not available');
    expect(money(0)).toBe('£0.00');
    render(<Risk value={null} />);
    expect(screen.getByText('Not available')).toBeInTheDocument();
  });
  it('announces API errors and empty states', () => {
    render(
      <>
        <ErrorState error={new Error('Inventory snapshot changed; refresh')} />
        <Empty>No forecast prepared</Empty>
      </>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('snapshot changed');
    expect(screen.getByText('No forecast prepared')).toBeVisible();
  });
});
