// Synthetic UI contract for the unified EMerge FEM · Experimental Run option (driven-like). No solver run.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import puppeteer from "puppeteer-core";
import { startStack, chromePath } from "./scenarios/stack.mjs";
import { Session } from "./scenarios/harness.mjs";

const stack = await startStack({ log: console.log });
let browser;
try {
  browser = await puppeteer.launch({
    executablePath: await chromePath(), headless: true,
    args: ["--no-sandbox", "--enable-unsafe-swiftshader"],
  });
  await mkdir(".impeccable/review", { recursive: true });
  for (const lang of ["en", "tr"]) {
    const context = await browser.createBrowserContext();
    const page = await context.newPage();
    await page.setViewport({ width: 1100, height: 900 });
    await page.evaluateOnNewDocument(language => localStorage.setItem("fairbeam.generalSettings", JSON.stringify({ language })), lang);
    const s = new Session(page, { lang, scenario: "emerge-antenna", url: stack.url });
    let healthEmerge = 1;
    let submitted;
    await page.setRequestInterception(true);
    page.on("request", async request => {
      const pathname = new URL(request.url()).pathname;
      try {
        if (pathname === "/api/health") {
          const response = await fetch(`${stack.apiUrl}/api/health`);
          const body = await response.json();
          body.emerge = healthEmerge;
          return void request.respond({
            status: 200, contentType: "application/json", body: JSON.stringify(body),
          });
        }
        if (pathname === "/api/research/probe") {
          return void request.respond({
            status: 200, contentType: "application/json",
            body: JSON.stringify({ backend: "emerge", available: true }),
          });
        }
        if (pathname === "/api/research/runs" && request.method() === "POST") {
          submitted = JSON.parse(request.postData());
          return void request.respond({
            status: 400, contentType: "application/json",
            body: JSON.stringify({ error: "Synthetic unsupported Design" }),
          });
        }
        void request.continue();
      } catch (error) {
        void request.abort("failed").catch(() => {});
        throw error;
      }
    });

    await page.goto(stack.url, { waitUntil: "domcontentloaded" });
    await s.wait(".home");
    await page.click('input[name="home-template"][value="patch"]');
    await s.fill(await s.field(await s.T("home.newProject.name")), `EMerge UI ${lang}`, { blur: false });
    await s.click("home.newProject.create"); await s.wait(".rb");
    await s.click("ribbon.tab.sim", { sel: ".rb-tab" });
    // Run chrome shows the active engine name (default openEMS), not ribbon.sim.run.
    await s.click("ribbon.sim.runEngine", { sel: ".rb-btn", params: { engine: "openEMS" } });
    await s.wait(".rd-dialog");
    // Unified gate is health.emerge >= 3 (legacy dual options removed).
    assert.equal(await page.$$eval('.rd-solver select option[value="emerge"]', rows => rows.length), 0,
      "emerge hidden when health.emerge < 3");
    assert.equal(await page.$$eval('.rd-solver select option[value="emerge-driven"]', rows => rows.length), 0,
      "legacy emerge-driven removed");

    healthEmerge = 3;
    await page.evaluate(async () => {
      const { probeServer } = await import("/src/runner/store.ts");
      await probeServer();
    });
    await page.waitForFunction(() => document.querySelector('.rd-solver select option[value="emerge"]'));
    await page.select(".rd-solver select", "emerge");
    await s.wait('[data-testid="emerge-run-form"]');
    assert.equal(await page.$("#rd-form"), null, "FDTD controls unmounted for EMerge");
    assert.ok(await page.$eval('[data-testid="emerge-run-form"] button[type=submit]', e => e.disabled),
      "acceptance required before submit");

    for (const [key, val] of Object.entries({ f_min_hz: "2.0", f_max_hz: "3.0", points: "5", padding_mm: "40", feed_width_mm: "1", air_height_mm: "6.4" })) {
      await s.fill(await s.field(await s.T(`emergeExp.${key}`)), val);
    }
    await page.select('[data-testid="emerge-run-resolution"]', "fine");
    assert.ok(await page.$eval('[data-testid="emerge-run-form"] button[type=submit]', e => e.disabled),
      "still disabled without finite-feed acceptance");
    await page.click('[data-testid="emerge-run-accept-finite"]');
    assert.equal(await page.$eval('[data-testid="emerge-run-form"] button[type=submit]', e => e.disabled), false);
    await page.screenshot({ path: `.impeccable/review/emerge-antenna-${lang}.png` });

    await page.click('[data-testid="emerge-run-form"] button[type=submit]');
    await page.waitForFunction(() => document.querySelector('[data-testid="emerge-run-form"] [role=alert]')?.textContent.includes("Synthetic unsupported Design"));
    assert.equal(submitted.backend, "emerge");
    assert.equal(submitted.settings.analysis, "emerge_nport");
    assert.equal(submitted.settings.accept_finite_feed, true);
    assert.equal(submitted.settings.resolution, "fine");
    assert.equal(submitted.settings.approximate_metals, false);
    assert.equal(submitted.settings.f_min_hz, 2e9);
    assert.equal(submitted.settings.f_max_hz, 3e9);
    assert.equal(submitted.settings.points, 5);
    assert.equal(submitted.settings.padding_mm, 40);
    assert.equal(submitted.settings.feed_width_mm, 1);
    assert.ok(submitted.design?.model?.id);

    // Synthetic completed Design result (labelled synthetic); not a solver run.
    page.removeAllListeners("request");
    const job = {
      id: `emerge-driven-${lang}`, kind: "research", status: "done", name: "EMerge patch",
      created: 1, created_iso: "2026-11-04T12:00:00Z", error: null, bundle: null,
      research: { backend: "emerge", settings: submitted.settings },
      result: {
        schema: "fairbeam.emerge-driven-result/1", status: "results_exported",
        backend: "emerge", frequency_hz: [2e9, 2.5e9, 3e9],
        s11_re: [0.1, 0.2, 0.1], s11_im: [0, 0, 0], z_ref: 50,
        precision_converged: false, gain_qualified: false,
        phasor_convention: "exp(+i omega t)",
        provenance: { synthetic: true },
        limitations: ["synthetic placeholder"],
      },
    };
    page.on("request", request => {
      const path = new URL(request.url()).pathname;
      if (path === "/api/research/runs" || path === `/api/research/runs/${job.id}`) {
        return void request.respond({
          status: 200, contentType: "application/json",
          body: JSON.stringify(path.endsWith(job.id) ? job : { runs: [job] }),
        });
      }
      void request.continue();
    });
    await page.evaluate(async id => {
      (await import("/src/runner/designRun.ts")).setRunDialogOpen(false);
      (await import("/src/runner/researchState.ts")).openResearch(id, "emerge", true);
    }, job.id);
    await page.waitForSelector(".research-results");
    assert.match(await page.$eval(".research-results", e => e.textContent), /synthetic/i,
      "synthetic result must be labelled synthetic");
    assert.ok(await page.$(".research-results .status-warn"), "uncertified result warning");
    await context.close();
  }
  console.log("PASS: EN/TR unified EMerge option health gate, acceptance, submit body, synthetic result label.");
} finally {
  await browser?.close();
  await stack.stop();
}
