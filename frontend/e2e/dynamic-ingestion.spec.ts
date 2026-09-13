import { test, expect } from "@playwright/test";
import { mockCorpus } from "./mock-corpus";

const CHUNK = {
  chunk_id: "NVDA_2026_10K_risk_factors_47",
  text: "NVIDIA relies on independent foundries for wafer fabrication.",
  company: "NVDA",
  fiscal_year: 2026,
  section: "risk_factors",
  score: 0.93,
};

test("ingestie dinamica — banner pentru compania adaugata in corpus", async ({ page }) => {
  await page.route("**/query", async (route) => {
    await route.fulfill({
      json: {
        answer: "NVIDIA depinde de foundry-uri independente [NVDA_2026_10K_risk_factors_47].",
        sources: [CHUNK.chunk_id],
        retrieved_chunks: [CHUNK],
        persona: "investment_firm",
        query_type: "risk_analysis",
        cost_usd: 0.067291,
        latency_ms: 493706,
        langsmith_trace_id: "trace-nvda-1",
        status: "valid",
        ingested_entities: ["NVDA"],
        ingestion_errors: [],
      },
    });
  });

  await mockCorpus(page);
  await page.goto("/");
  await page.getByPlaceholder(/Ask about/).fill("What does Nvidia report about supply chain risk?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(/Added to the corpus during this query/)).toBeVisible();
  // "NVDA" apare de doua ori (bannerul din main si cutia din sidebar) — .first() e suficient aici.
  await expect(page.getByText("NVDA", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/depinde de foundry-uri/)).toBeVisible();
});

test("ingestie esuata — eroare explicita per companie, raspunsul tot apare", async ({ page }) => {
  await page.route("**/query", async (route) => {
    await route.fulfill({
      json: {
        answer: "There is no information about Alibaba in the provided context.",
        sources: [],
        retrieved_chunks: [],
        persona: "legal",
        query_type: "risk_analysis",
        cost_usd: 0.0038,
        latency_ms: 14778,
        langsmith_trace_id: "trace-baba-1",
        status: "valid",
        ingested_entities: [],
        ingestion_errors: ["BABA: no 10-K filings found on SEC EDGAR for CIK 0001577552"],
      },
    });
  });

  await mockCorpus(page);
  await page.goto("/");
  await page.getByPlaceholder(/Ask about/).fill("What does Alibaba report about regulatory risk?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(/Could not add some companies to the corpus/)).toBeVisible();
  await expect(page.getByText(/no 10-K filings found on SEC EDGAR/)).toBeVisible();
  // esecul de ingestie nu trebuie sa ascunda raspunsul generat din corpusul existent
  await expect(page.getByText(/no information about Alibaba/)).toBeVisible();
});
