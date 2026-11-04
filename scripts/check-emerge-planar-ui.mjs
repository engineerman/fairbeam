// Synthetic UI contract for the experimental EMerge planar two-port Run option. No solver run.
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
    await s.click("ribbon.sim.run", { sel: ".rb-btn" });
    await s.wait(".rd-dialog");
    // emerge: 2 shows antenna but must hide planar (needs health.emerge >= 3).
    assert.ok(await page.$('.rd-solver select option[value="emerge-driven"]'),
      "emerge-driven still shown when health.emerge = 2");
    assert.equal(await page.$$eval('.rd-solver select option[value="emerge-planar"]', rows => rows.length), 0,
      "emerge-planar hidden when health.emerge < 3");

    healthEmerge = 3;
    await page.evaluate(async () => {
      const { probeServer } = await import("/src/runner/store.ts");
      await probeServer();
    });
    await page.waitForFunction(() => document.querySelector('.rd-solver select option[value="emerge-planar"]'));
    await page.select(".rd-solver select", "emerge-planar");
    await s.wait('[data-testid="emerge-planar-form"]');
    assert.equal(await page.$("#rd-form"), null, "FDTD controls unmounted for EMerge planar");
    assert.ok(await page.$eval('[data-testid="emerge-planar-form"] button[type=submit]', e => e.disabled),
      "acceptance required before submit");
    assert.equal(await page.$('[data-testid="emerge-planar-padding"]'), null,
      "padding hidden for default shielded enclosure");

    for (const [key, val] of Object.entries({ f_min_hz: "0.75", f_max_hz: "1.25", points: "5", air_height_mm: "8" })) {
      await s.fill(await s.field(await s.T(`emergePlanar.${key}`)), val);
    }
    await page.select('[data-testid="emerge-planar-resolution"]', "fine");
    assert.ok(await page.$eval('[data-testid="emerge-planar-form"] button[type=submit]', e => e.disabled),
      "still disabled without lumped-terminal acceptance");
    await page.click('[data-testid="emerge-planar-accept"]');
    assert.equal(await page.$eval('[data-testid="emerge-planar-form"] button[type=submit]', e => e.disabled), false);

    // Shielded submit: padding must not be sent.
    await page.click('[data-testid="emerge-planar-form"] button[type=submit]');
    await page.waitForFunction(() => document.querySelector('[data-testid="emerge-planar-form"] [role=alert]')?.textContent.includes("Synthetic unsupported Design"));
    assert.equal(submitted.backend, "emerge");
    assert.equal(submitted.settings.analysis, "planar_two_port");
    assert.equal(submitted.settings.accept_lumped_terminals, true);
    assert.equal(submitted.settings.enclosure, "shielded");
    assert.equal(submitted.settings.resolution, "fine");
    assert.equal(submitted.settings.approximate_metals, false);
    assert.equal(submitted.settings.f_min_hz, 0.75e9);
    assert.equal(submitted.settings.f_max_hz, 1.25e9);
    assert.equal(submitted.settings.points, 5);
    assert.equal(submitted.settings.air_height_mm, 8);
    assert.equal("padding_mm" in submitted.settings, false, "padding_mm omitted for shielded");
    assert.ok(submitted.design?.model?.id);

    // Open enclosure: padding visible and sent.
    submitted = undefined;
    await page.select('[data-testid="emerge-planar-enclosure"]', "open");
    await page.waitForSelector('[data-testid="emerge-planar-padding"]');
    await s.fill(await s.field(await s.T("emergePlanar.padding_mm")), "10");
    await page.click('[data-testid="emerge-planar-form"] button[type=submit]');
    await page.waitForFunction(() => {
      const alert = document.querySelector('[data-testid="emerge-planar-form"] [role=alert]');
      return alert?.textContent.includes("Synthetic unsupported Design");
    });
    assert.equal(submitted.settings.enclosure, "open");
    assert.equal(submitted.settings.padding_mm, 10);

    await page.screenshot({ path: `.impeccable/review/emerge-planar-${lang}.png` });
    await context.close();
  }
  console.log("PASS: EN/TR EMerge planar option health gate, acceptance, shielded/open padding, submit body.");
} finally {
  await browser?.close();
  await stack.stop();
}
