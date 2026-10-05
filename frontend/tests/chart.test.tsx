import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { DemandChart } from '../src/components/charts/DemandChart';

it('provides chart summary and keyboard inspectable data points', () => {
  render(
    <DemandChart
      cutoff="2024-01-01"
      sales={[{ day: '2024-01-01', units: 5 }]}
      points={[{ day: '2024-01-02', yhat: 6, lower: 3, upper: 9 }]}
    />,
  );
  expect(screen.getByRole('img', { name: /Demand through/ })).toHaveAccessibleName(
    /1 forecast points/,
  );
  expect(screen.getByLabelText(/02 Jan 2024: 6 units/)).toHaveAttribute('tabindex', '0');
});
