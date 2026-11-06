// Synthetic UI contract for the unified EMerge FEM · Experimental Run option. No solver run.
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
    const s = new Session(page, { lang, scenario: "emerge-planar", url: stack.url });
    let healthEmerge = 2;
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
    await s.fill(await s.field(await s.T("home.newProject.name")), `EMerge planar UI ${lang}`, { blur: false });
    await s.click("home.newProject.create"); await s.wait(".rb");
    await s.click("ribbon.tab.sim", { sel: ".rb-tab" });
    // Run chrome shows the active engine name (default openEMS), not ribbon.sim.run.
    await s.click("ribbon.sim.runEngine", { sel: ".rb-btn", params: { engine: "openEMS" } });
    await s.wait(".rd-dialog");
    // Unified option needs health.emerge >= 3; dual emerge-driven / emerge-planar are gone.
    assert.equal(await page.$$eval('.rd-solver select option[value="emerge"]', rows => rows.length), 0,
      "emerge hidden when health.emerge < 3");
    assert.equal(await page.$$eval('.rd-solver select option[value="emerge-driven"]', rows => rows.length), 0,
      "legacy emerge-driven removed");
    assert.equal(await page.$$eval('.rd-solver select option[value="emerge-planar"]', rows => rows.length), 0,
      "legacy emerge-planar removed");

    healthEmerge = 3;
    await page.evaluate(async () => {
      const { probeServer } = await import("/src/runner/store.ts");
      await probeServer();
    });
    await page.waitForFunction(() => document.querySelector('.rd-solver select option[value="emerge"]'));
    await page.select(".rd-solver select", "emerge");
    await s.wait('[data-testid="emerge-run-form"]');
    assert.equal(await page.$("#rd-form"), null, "FDTD controls unmounted for EMerge");
    // Patch template uses Discrete/lumped → finite-feed accept + driven feed fields.
    assert.ok(await page.$('[data-testid="emerge-run-port-note"]'),
      "finite-feed note shown as status-warn");
    assert.ok(await page.$('[data-testid="emerge-run-accept-finite"]'),
      "finite-feed acceptance required");
    assert.ok(await page.$('[data-testid="emerge-run-padding"]'),
      "padding shown for driven fallback on lumped ports");
    assert.ok(await page.$('[data-testid="emerge-run-enclosure"]'),
      "planar enclosure shown when unsure (lumped)");

    for (const [key, val] of Object.entries({ f_min_hz: "0.75", f_max_hz: "1.25", points: "5", air_height_mm: "8" })) {
      await s.fill(await s.field(await s.T(`emergeExp.${key}`)), val);
    }
    await page.select('[data-testid="emerge-run-resolution"]', "fine");
    assert.ok(await page.$eval('[data-testid="emerge-run-form"] button[type=submit]', e => e.disabled),
      "still disabled without finite-feed acceptance");
    await page.click('[data-testid="emerge-run-accept-finite"]');
    assert.equal(await page.$eval('[data-testid="emerge-run-form"] button[type=submit]', e => e.disabled), false);

    // Shielded submit: padding still sent for driven fallback; analysis is emerge_nport.
    await page.click('[data-testid="emerge-run-form"] button[type=submit]');
    await page.waitForFunction(() => document.querySelector('[data-testid="emerge-run-form"] [role=alert]')?.textContent.includes("Synthetic unsupported Design"));
    assert.equal(submitted.backend, "emerge");
    assert.equal(submitted.settings.analysis, "emerge_nport");
    assert.equal(submitted.settings.accept_finite_feed, true);
    assert.equal(submitted.settings.enclosure, "shielded");
    assert.equal(submitted.settings.resolution, "fine");
    assert.equal(submitted.settings.approximate_metals, false);
    assert.equal(submitted.settings.f_min_hz, 0.75e9);
    assert.equal(submitted.settings.f_max_hz, 1.25e9);
    assert.equal(submitted.settings.points, 5);
    assert.equal(submitted.settings.air_height_mm, 8);
    assert.equal(submitted.settings.padding_mm, 10, "padding kept for driven fallback");
    assert.ok(submitted.design?.model?.id);

    // Open enclosure: padding still visible and sent.
    submitted = undefined;
    await page.select('[data-testid="emerge-run-enclosure"]', "open");
    await page.waitForSelector('[data-testid="emerge-run-padding"]');
    await s.fill(await s.field(await s.T("emergeExp.padding_mm")), "12");
    await page.click('[data-testid="emerge-run-form"] button[type=submit]');
    await page.waitForFunction(() => {
      const alert = document.querySelector('[data-testid="emerge-run-form"] [role=alert]');
      return alert?.textContent.includes("Synthetic unsupported Design");
    });
    assert.equal(submitted.settings.enclosure, "open");
    assert.equal(submitted.settings.padding_mm, 12);

    await page.screenshot({ path: `.impeccable/review/emerge-planar-${lang}.png` });
    await context.close();
  }
  console.log("PASS: EN/TR unified EMerge option health gate, acceptance, shielded/open padding, submit body.");
} finally {
  await browser?.close();
  await stack.stop();
}
