import { expect, test } from '@playwright/test';

test('demo → product → explanation → scenario → comparison → export', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Inventory overview' })).toBeVisible();
  await expect(page.getByText('synthetic data')).toBeVisible();
  await expect(page.getByRole('img', { name: /and 28 forecast points/ })).toBeVisible();
  await page.screenshot({
    path: `test-results/${info.project.name}-dashboard.png`,
    fullPage: true,
  });
  await page.getByRole('navigation').getByRole('link', { name: 'Products', exact: true }).click();
  await page.getByRole('link', { name: 'Inspect →' }).first().click();
  await expect(page.getByRole('heading', { name: 'Observed sales & forecast' })).toBeVisible();
  await page.getByRole('link', { name: 'View purchase explanation' }).click();
  await page.getByRole('button', { name: 'Explain', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: /purchase calculation/ }).first()).toBeVisible();
  await page
    .getByRole('navigation')
    .getByRole('link', { name: 'Scenario lab', exact: true })
    .click();
  await page.getByRole('button', { name: 'Supplier delay', exact: true }).click();
  await expect(
    page.getByRole('spinbutton', { name: 'Extra delivery days', exact: true }),
  ).toHaveValue('4');
  await page.getByRole('button', { name: 'Run simulation' }).click();
  await expect(page.getByRole('columnheader', { name: 'Forecast policy' })).toBeVisible({
    timeout: 150000,
  });
  await expect(page.getByRole('rowheader', { name: 'Fill rate', exact: true })).toBeVisible();
  await page.screenshot({ path: `test-results/${info.project.name}-scenario.png`, fullPage: true });
  await page
    .getByRole('navigation')
    .getByRole('link', { name: 'Replenishment', exact: true })
    .click();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download plan CSV' }).click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toMatch(/^stockpilot-plan-.*\.csv$/);
  await page.getByRole('navigation').getByRole('link', { name: 'Assistant', exact: true }).click();
  await page.getByRole('button', { name: 'Why should I order DEMO-004?' }).click();
  await page.getByRole('button', { name: 'Ask →', exact: true }).click();
  await expect(page.getByText(/get_recommendation_explanation/)).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
  expect(errors).toEqual([]);
});
