import { test, expect } from "@playwright/test";
import { mockCorpus } from "./mock-corpus";

test("reasoning trace — ascuns implicit, vizibil dupa click", async ({ page }) => {
  await page.route("**/query", async (route) => {
    await route.fulfill({
      json: {
        answer: "Apple's cash position was strong [c1].",
        sources: ["c1"],
        retrieved_chunks: [
          {
            chunk_id: "c1",
            text: "Cash and equivalents: $29.9B.",
            company: "AAPL",
            fiscal_year: 2023,
            section: "market_risk",
            score: 0.91,
          },
        ],
        persona: "treasury",
        query_type: "factual",
        cost_usd: 0.001234,
        latency_ms: 842,
        langsmith_trace_id: "trace-abc-123",
        status: "valid",
        ingested_entities: [],
        ingestion_errors: [],
        ingestion_details: [],
        reasoning_trace: [
          "Classified as **treasury** / **factual** — the question asks about liquidity.",
          "Companies mentioned already in corpus: AAPL",
          "Searched market_risk, financial_statements sections (treasury) — 8 candidate chunks found",
          "Reranked to top 8 chunks via Vertex AI (top score 0.91)",
          "Context verified as sufficient",
          "Generated answer citing 1 source chunks",
        ],
      },
    });
  });

  await mockCorpus(page);
  await page.goto("/");
  await page.getByPlaceholder(/Ask about/).fill("What is Apple's liquidity level?");
  await page.getByRole("button", { name: "Send" }).click();

  const toggle = page.getByText(/How this answer was put together/);
  await expect(toggle).toBeVisible();
  await expect(page.getByText(/Classified as/)).not.toBeVisible();

  await toggle.click();
  await expect(page.getByText(/Classified as \*\*treasury\*\*/)).toBeVisible();
  await expect(page.getByText(/Generated answer citing 1 source/)).toBeVisible();
});

test("fara reasoning_trace — sectiunea nu apare deloc", async ({ page }) => {
  await page.route("**/query", async (route) => {
    await route.fulfill({
      json: {
        answer: "Apple's cash position was strong [c1].",
        sources: ["c1"],
        retrieved_chunks: [],
        persona: "treasury",
        query_type: "factual",
        cost_usd: 0.001234,
        latency_ms: 842,
        langsmith_trace_id: "trace-abc-123",
        status: "valid",
        ingested_entities: [],
        ingestion_errors: [],
        ingestion_details: [],
        reasoning_trace: [],
      },
    });
  });

  await mockCorpus(page);
  await page.goto("/");
  await page.getByPlaceholder(/Ask about/).fill("What is Apple's liquidity level?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(/strong/)).toBeVisible();
  await expect(page.getByText(/How this answer was put together/)).not.toBeVisible();
});
