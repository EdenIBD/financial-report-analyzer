import { test, expect } from "@playwright/test";

test("eroare backend — mesaj clar, nu UI gol/spart", async ({ page }) => {
  await page.route("**/query", async (route) => {
    await route.abort("connectionrefused");
  });

  await page.goto("/");
  await page.getByPlaceholder(/Intreaba despre/).fill("Care e nivelul de lichiditate al Apple?");
  await page.getByRole("button", { name: "Trimite" }).click();

  await expect(page.getByText(/Nu s-a putut contacta backend-ul/)).toBeVisible();
  // UI-ul de baza (titlu, input, buton) tot trebuie sa fie prezent — nu pagina goala/sparta.
  await expect(page.getByRole("heading", { name: "Financial Report Analyzer" })).toBeVisible();
  await expect(page.getByPlaceholder(/Intreaba despre/)).toBeVisible();
});
