import { test, expect } from '@playwright/test';
import { mockCorpus } from './mock-corpus';

const base = {persona:'investment_firm',query_type:'factual',cost_usd:0.01,latency_ms:500,
  langsmith_trace_id:null,ingested_entities:[],ingestion_errors:[],ingestion_details:[],reasoning_trace:[]};

test('historical NVIDIA filing displays the requested year and evidence', async ({page}) => {
  const id='NVDA_2023_10K_financial_statements_0';
  await mockCorpus(page);
  await page.route('**/query',route=>route.fulfill({json:{...base,status:'valid',
    answer:`NVIDIA FY2023 evidence [${id}]`,sources:[id],
    retrieved_chunks:[{chunk_id:id,company:'NVDA',fiscal_year:2023,section:'financial_statements',text:'Historical NVIDIA evidence',score:.9}],
    ingested_entities:['NVDA'],ingestion_details:[{ticker:'NVDA',company:'NVIDIA CORP',fiscal_year:2023,filing_type:'10-K',chunks:10}]}}));
  await page.goto('/');
  await page.getByPlaceholder(/Ask about/).fill('Check NVDA financial report from 2023 and summarize it');
  await page.getByRole('button',{name:'Send'}).click();
  await expect(page.getByText('NVIDIA CORP · 10-K · FY2023')).toBeVisible();
  await page.getByRole('button',{name:/Show retrieved chunks/}).click();
  await expect(page.getByText('Historical NVIDIA evidence')).toBeVisible();
  await expect(page.getByText(/GOOGL_2025|NVDA_2026/)).toHaveCount(0);
});

test('unresolved registrant shows abstention without unrelated sources',async ({page})=>{
  await mockCorpus(page);
  await page.route('**/query',route=>route.fulfill({json:{...base,status:'abstained',
    answer:'I could not obtain evidence for the requested company and fiscal year.',sources:[],retrieved_chunks:[],
    ingestion_errors:['Taco Bell Funding, LLC: could not resolve an exact registrant in the SEC ticker catalog. No other company was substituted.']}}));
  await page.goto('/');
  await page.getByPlaceholder(/Ask about/).fill('Taco Bell Funding, LLC 2023');
  await page.getByRole('button',{name:'Send'}).click();
  await expect(page.getByText(/could not resolve an exact registrant/)).toBeVisible();
  await expect(page.getByText(/I could not obtain evidence/)).toBeVisible();
  await expect(page.getByRole('button',{name:/Show retrieved chunks/})).toHaveCount(0);
});

test('eagle matches reference placement without intercepting controls',async({page})=>{
  await mockCorpus(page);await page.goto('/');
  const eagle=page.locator('.eagle-watermark');
  await expect(eagle).toBeVisible();
  await expect(eagle).toHaveCSS('opacity','0.08');
  await expect(eagle).toHaveCSS('pointer-events','none');
  await expect(eagle).toHaveCSS('width','460px');
  await expect(eagle).toHaveAttribute('alt','');
  const boxes=await page.locator('.sidebar').evaluate(el=>{
    const s=el.getBoundingClientRect(), i=el.querySelector('img')!.getBoundingClientRect();
    return {expected:s.y+s.height*.44,actual:i.y+i.height/2};
  });
  expect(Math.abs(boxes.expected-boxes.actual)).toBeLessThan(2);
});
