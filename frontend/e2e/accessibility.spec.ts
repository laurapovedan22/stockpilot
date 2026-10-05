import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('main workspace pages pass automated WCAG AA checks', async ({ page }, info) => {
  for (const path of [
    '/',
    '/products',
    '/forecasts',
    '/replenishment',
    '/scenarios',
    '/quality',
    '/assistant',
    '/about',
  ]) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await page.waitForLoadState('networkidle');
    const result = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();
    await info.attach(`axe-${path.replaceAll('/', '') || 'dashboard'}`, {
      body: JSON.stringify(result.violations, null, 2),
      contentType: 'application/json',
    });
    expect(
      result.violations.map((issue) => ({
        id: issue.id,
        impact: issue.impact,
        count: issue.nodes.length,
        nodes: issue.nodes
          .slice(0, 3)
          .map((node) => ({ target: node.target, summary: node.failureSummary })),
      })),
      `WCAG violations on ${path}`,
    ).toEqual([]);
  }
});
