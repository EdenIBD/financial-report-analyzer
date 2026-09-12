import { test, expect } from "@playwright/test";

test("happy path — query factual despre Apple", async ({ page }) => {
  await page.route("**/query", async (route) => {
    await route.fulfill({
      json: {
        answer: "Apple raporteaza o pozitie solida de lichiditate [c1].",
        sources: ["c1"],
        retrieved_chunks: [
          {
            chunk_id: "c1",
            text: "Numerar si echivalente de numerar la 30 sept 2023: $29.9 miliarde.",
            company: "AAPL",
            fiscal_year: 2023,
            section: "Item7A",
            score: 0.91,
          },
        ],
        persona: "treasury",
        query_type: "factual",
        cost_usd: 0.001234,
        latency_ms: 842,
        langsmith_trace_id: "trace-abc-123",
        status: "valid",
      },
    });
  });

  await page.goto("/");
  await page.getByPlaceholder(/Intreaba despre/).fill("Care e nivelul de lichiditate al Apple?");
  await page.getByRole("button", { name: "Trimite" }).click();

  await expect(page.getByText("treasury")).toBeVisible();
  await expect(page.getByText("factual")).toBeVisible();
  await expect(page.getByText(/pozitie solida de lichiditate/)).toBeVisible();

  const citation = page.getByRole("button", { name: "[c1]" });
  await expect(citation).toBeVisible();

  await citation.click();
  await expect(page.getByText(/29.9 miliarde/)).toBeVisible();
});
