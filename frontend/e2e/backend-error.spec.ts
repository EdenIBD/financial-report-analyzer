import { test, expect } from "@playwright/test";
import { mockCorpus } from "./mock-corpus";

test("eroare backend — mesaj clar, nu UI gol/spart", async ({ page }) => {
  await page.route("**/query", async (route) => {
    await route.abort("connectionrefused");
  });

  await mockCorpus(page);
  await page.goto("/");
  await page.getByPlaceholder(/Ask about/).fill("Care e nivelul de lichiditate al Apple?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(/Could not reach the backend/)).toBeVisible();
  // UI-ul de baza (titlu, input, buton) tot trebuie sa fie prezent — nu pagina goala/sparta.
  await expect(page.getByRole("heading", { name: "Financial Report Analyzer" })).toBeVisible();
  await expect(page.getByPlaceholder(/Ask about/)).toBeVisible();
});
