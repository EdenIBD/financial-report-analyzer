import { test, expect } from "@playwright/test";

test("comparatie — query care mentioneaza doua companii", async ({ page }) => {
  await page.route("**/query", async (route) => {
    await route.fulfill({
      json: {
        answer:
          "Marja operationala a Google a crescut [c1], in timp ce Microsoft raporteaza o marja stabila [c2].",
        sources: ["c1", "c2"],
        retrieved_chunks: [
          {
            chunk_id: "c1",
            text: "Marja operationala Google: 32% in ultimul an fiscal.",
            company: "GOOGL",
            fiscal_year: 2023,
            section: "Item7",
            score: 0.88,
          },
          {
            chunk_id: "c2",
            text: "Marja operationala Microsoft: 44% in ultimul an fiscal.",
            company: "MSFT",
            fiscal_year: 2023,
            section: "Item7",
            score: 0.85,
          },
        ],
        persona: "investment_firm",
        query_type: "comparison",
        cost_usd: 0.002,
        latency_ms: 1200,
        langsmith_trace_id: "trace-cmp-1",
        status: "valid",
      },
    });
  });

  await page.goto("/");
  await page
    .getByPlaceholder(/Intreaba despre/)
    .fill("Cum se compara marja operationala a Google si Microsoft?");
  await page.getByRole("button", { name: "Trimite" }).click();

  await expect(page.getByText(/Google/).first()).toBeVisible();
  await expect(page.getByText(/Microsoft/).first()).toBeVisible();

  await page.getByRole("button", { name: /fragmentele recuperate/ }).click();

  await expect(page.getByText(/GOOGL 2023/)).toBeVisible();
  await expect(page.getByText(/MSFT 2023/)).toBeVisible();
});
