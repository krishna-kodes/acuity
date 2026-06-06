import { test, expect } from "@playwright/test";
import path from "path";

const PROJECT_ID = "42";

const MOCK_PROJECT = {
  id: PROJECT_ID,
  name: "Playwright Test Project",
  domain: null,
  status: "draft",
  current_phase: 1,
  created_at: new Date().toISOString(),
};

test.beforeEach(async ({ page }) => {
  // Mock list projects (dashboard)
  await page.route("**/api/v1/projects", async (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(MOCK_PROJECT) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MOCK_PROJECT]) });
  });

  // Mock upload document
  await page.route(`**/api/v1/projects/${PROJECT_ID}/documents`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: 1, project_id: PROJECT_ID, filename: "test.pdf", status: "ready" }),
    })
  );

  // Mock redaction decisions — no PII detected
  await page.route(`**/api/v1/projects/${PROJECT_ID}/redaction-decisions`, (route) => {
    if (route.request().method() === "PATCH") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ applied: 0, skipped: 0, status: "ingestion_skipped" }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });

  // Mock TBDs — none open
  await page.route(`**/api/v1/projects/${PROJECT_ID}/tbds`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
});

test("upload form creates project and redirects to redaction", async ({ page }) => {
  await page.goto("/projects/new");

  // Fill project name
  await page.locator("#proj-name").fill("Playwright Test Project");

  // Attach file via the hidden file input
  const minimalPdf = Buffer.from("%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\n0 1\n0000000000 65535 f\ntrailer<</Size 1>>\nstartxref\n18\n%%EOF");
  await page.locator('input[type="file"]').setInputFiles({
    name: "requirements.pdf",
    mimeType: "application/pdf",
    buffer: minimalPdf,
  });

  // Submit
  await page.getByRole("button", { name: /create project/i }).click();

  // Should redirect to redaction page
  await expect(page).toHaveURL(new RegExp(`/projects/${PROJECT_ID}/redaction`), { timeout: 8000 });
});

test("redaction page shows proceed enabled when no PII detected", async ({ page }) => {
  await page.goto(`/projects/${PROJECT_ID}/redaction`);

  // "All detections resolved" message should appear
  await expect(page.getByText(/all detections resolved/i)).toBeVisible({ timeout: 8000 });

  // Proceed button should be enabled
  await expect(page.getByRole("button", { name: /proceed/i })).toBeEnabled();
});

test("redaction proceed navigates to chat page", async ({ page }) => {
  await page.goto(`/projects/${PROJECT_ID}/redaction`);

  await expect(page.getByRole("button", { name: /proceed/i })).toBeEnabled({ timeout: 8000 });
  await page.getByRole("button", { name: /proceed/i }).click();

  await expect(page).toHaveURL(new RegExp(`/projects/${PROJECT_ID}/chat`), { timeout: 8000 });
});
