import { expect, test } from '@playwright/test';

test('optional UCI workspace shows all selected planning products after switching dataset', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Inventory overview' })).toBeVisible();
  const dataset = page.getByRole('combobox', { name: 'Selected dataset' });
  const historical = dataset.locator('option').filter({ hasText: 'UCI Online Retail II' });
  test.skip(
    (await historical.count()) === 0,
    'Optional UCI dataset is not prepared in this environment',
  );
  const id = await historical.getAttribute('value');
  await dataset.selectOption(id!);
  await expect(page.getByText('historical data', { exact: true })).toBeVisible();
  await expect(page.getByRole('img', { name: /and 28 forecast points/ })).toBeVisible();
  await page.getByRole('navigation').getByRole('link', { name: 'Forecasts', exact: true }).click();
  await expect(
    page.getByRole('combobox', { name: 'Product', exact: true }).locator('option'),
  ).toHaveCount(20);
  await expect(page.getByRole('img', { name: /and 28 forecast points/ })).toBeVisible();
  await expect(page.getByText('Final test WAPE', { exact: true })).toBeVisible();
});
