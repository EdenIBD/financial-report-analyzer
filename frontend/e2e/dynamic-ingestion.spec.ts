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
        ingestion_details: [{ ticker: "NVDA", company: "NVIDIA CORP", fiscal_year: 2026, filing_type: "10-K", chunks: 347 }],
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

  // Cardul de previzualizare document din sidebar, cu metadata reala
  await expect(page.getByText("nvda.html")).toBeVisible();
  await expect(page.getByText(/NVIDIA CORP · 10-K · FY2026/)).toBeVisible();
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
        ingestion_details: [],
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

test("comparatie cu doua companii necunoscute — una ingerata, cealalta blocata de limita", async ({ page }) => {
  // MAX_INGESTIONS_PER_QUERY = 1: a doua companie necunoscuta dintr-un query
  // de comparatie nu se ingereaza, dar trebuie sa apara ca eroare explicita,
  // nu ca esec tacut — banner-ul de succes si cel de eroare pot coexista.
  await page.route("**/query", async (route) => {
    await route.fulfill({
      json: {
        answer: "Tesla's margins are discussed [TSLA_2025_10K_mdna_3]; no data is available for Rivian yet.",
        sources: ["TSLA_2025_10K_mdna_3"],
        retrieved_chunks: [
          {
            chunk_id: "TSLA_2025_10K_mdna_3",
            text: "Automotive gross margin was 18.2%.",
            company: "TSLA",
            fiscal_year: 2025,
            section: "mdna",
            score: 0.87,
          },
        ],
        persona: "investment_firm",
        query_type: "comparison",
        cost_usd: 0.0512,
        latency_ms: 187321,
        langsmith_trace_id: "trace-tsla-rivn-1",
        status: "valid",
        ingested_entities: ["TSLA"],
        ingestion_errors: ["RIVN: per-query ingestion limit reached, not fetched"],
        ingestion_details: [
          { ticker: "TSLA", company: "Tesla, Inc.", fiscal_year: 2025, filing_type: "10-K", chunks: 210 },
        ],
      },
    });
  });

  await mockCorpus(page);
  await page.goto("/");
  await page.getByPlaceholder(/Ask about/).fill("Compare Tesla and Rivian margins");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(/Added to the corpus during this query/)).toBeVisible();
  await expect(page.getByText(/Could not add some companies to the corpus/)).toBeVisible();
  await expect(page.getByText(/RIVN: per-query ingestion limit reached/)).toBeVisible();
  await expect(page.getByText("tsla.html")).toBeVisible();
});
