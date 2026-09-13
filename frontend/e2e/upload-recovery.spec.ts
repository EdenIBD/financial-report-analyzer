import { test, expect } from '@playwright/test';

test('upload polling recovers after a transient failure', async ({ page }) => {
  let polls = 0;
  await page.route('**/corpus', route => route.fulfill({json: { companies: [], total_filings: 0, min_year: null, max_year: null } }));
  await page.route('**/documents/upload', route => route.fulfill({json: {document_id:'retry-upload',status:'processing'}}));
  await page.route('**/documents/retry-upload/status', route => {
    if (++polls === 1) return route.abort();
    return route.fulfill({json: {document_id:'retry-upload',status:'ready',original_filename:'filing.html',company:'Test Co',ticker:'TEST',filing_type:'10-K',fiscal_year:2024,sections_found:6,chunks_indexed:10,error_message:null}});
  });
  await page.goto('/');
  await page.locator('input[type=file]').setInputFiles({name:'filing.html',mimeType:'text/html',buffer:Buffer.from('<html/>')});
  await expect(page.getByText(/Could not reach the backend while checking/)).toBeVisible();
  await expect(page.getByText(/Ready — Test Co/)).toBeVisible({timeout:15000});
  await expect(page.getByText(/Could not reach the backend while checking/)).toHaveCount(0);
});
