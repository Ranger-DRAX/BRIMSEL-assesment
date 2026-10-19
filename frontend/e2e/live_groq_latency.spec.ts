import { test, expect } from "@playwright/test";

test.describe("Browser Live Latency Measurement", () => {
  test("measure Send-to-complete-checked-reply-render time with real backend", async ({
    page,
  }) => {
    // 1. Visit root page and complete setup
    await page.goto("/");
    await page.getByLabel(/Child's First Name or Nickname/i).fill("Timmy");
    await page.getByLabel(/I am a parent or adult supervisor/i).check();
    await page.getByRole("button", { name: /Start Learning with Pip/i }).click();

    await expect(page.getByRole("heading", { name: "Little English Buddy" })).toBeVisible();

    const samplePrompts = [
      "Hello Pip! I like blue birds.",
      "What is your favorite animal?",
      "Can we count to three?",
    ];

    const measurements: number[] = [];

    for (let i = 0; i < samplePrompts.length; i++) {
      const prompt = samplePrompts[i];
      const input = page.getByLabel(/Type a message to Pip/i);
      await input.fill(prompt);

      const sendBtn = page.getByRole("button", { name: "Send" });

      const startTime = Date.now();
      await sendBtn.click();

      // Wait until input is re-enabled and loading indicator disappears
      await expect(input).toBeEnabled({ timeout: 10000 });

      // Verify at least one assistant message appeared
      const bubbles = page.locator("main p");
      const count = await bubbles.count();
      expect(count).toBeGreaterThan(1);

      const endTime = Date.now();
      const elapsed = endTime - startTime;
      measurements.push(elapsed);
      console.log(`[Browser Turn ${i + 1}] Render Latency: ${elapsed} ms (Prompt: "${prompt}")`);

      // Polite pacing between turns
      await page.waitForTimeout(1000);
    }

    measurements.sort((a, b) => a - b);
    const p50 = measurements[Math.floor(measurements.length / 2)];
    console.log(`\n=== Browser Render Latency: p50 = ${p50} ms across ${measurements.length} turns ===`);
    expect(p50).toBeLessThan(3500);
  });
});
