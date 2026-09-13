import { Page } from "@playwright/test";

// Sidebar-ul face fetch la /corpus la montare; fara mock, testele ar depinde
// de un backend real pornit pe :8000 (fragil in CI) doar ca sa afiseze pastilele
// de companii — restul comportamentului testat nu are legatura cu /corpus.
export async function mockCorpus(page: Page) {
  await page.route("**/corpus", async (route) => {
    await route.fulfill({
      json: {
        companies: [
          { ticker: "AAPL", company: "Apple Inc." },
          { ticker: "MSFT", company: "Microsoft Corporation" },
          { ticker: "GOOGL", company: "Alphabet Inc." },
        ],
        filings_indexed: 14,
        fiscal_year_min: 2020,
        fiscal_year_max: 2026,
      },
    });
  });
}
