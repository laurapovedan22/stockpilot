import type { Numeric } from '../types/api';
export const number = (value: Numeric | null | undefined, digits = 0) =>
  value == null
    ? 'Not available'
    : new Intl.NumberFormat('en-GB', { maximumFractionDigits: digits }).format(Number(value));
export const money = (value: Numeric | null | undefined) =>
  value == null
    ? 'Not available'
    : new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(Number(value));
export const percent = (value: Numeric | null | undefined) =>
  value == null
    ? 'Not available'
    : new Intl.NumberFormat('en-GB', { style: 'percent', maximumFractionDigits: 1 }).format(
        Number(value),
      );
export const date = (value: string) =>
  new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(value));
export const modelName = (value: string) =>
  ({
    seasonal_naive: 'Seasonal naïve (7 days)',
    moving_average: 'Moving average (28 days)',
    xgboost: 'Global XGBoost',
    selected_model: 'Forecast policy',
    no_purchase: 'No new purchases',
  })[value] ?? value;
