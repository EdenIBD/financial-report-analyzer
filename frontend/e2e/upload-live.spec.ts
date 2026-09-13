import { test, expect } from '@playwright/test';
import path from 'path';

test.skip(process.env.RUN_LIVE_UPLOAD !== '1', 'Requires Docker and real SEC fixtures; performs paid ingestion.');
test.use({ baseURL: 'http://localhost:3000' });

test('real legacy filing reports unsupported inline XBRL', async ({ page }) => {
  await page.goto('/');
  await page.locator('input[type=file]').setInputFiles(path.resolve('../data/raw/upload-evaluation/yum_2015_10k.html'));
  await expect(page.getByText(/Failed:.*Older filings without inline XBRL/)).toBeVisible({ timeout: 60000 });
});

test('real Winmark 10-Q reaches ready after parsing and indexing', async ({ page }) => {
  test.setTimeout(900000);
  await page.goto('/');
  await page.locator('input[type=file]').setInputFiles(path.resolve('../data/raw/upload-evaluation/wina_2024-09-28_10q.html'));
  await expect(page.getByText(/Ready —.*WINA/)).toBeVisible({ timeout: 850000 });
});
