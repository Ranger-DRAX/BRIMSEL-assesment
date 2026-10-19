import { test, expect } from "@playwright/test";

test.describe("Little English Buddy - Full Journey", () => {
  test("complete user journey: onboarding, placement, chat, learn, hint, settings", async ({
    page,
  }) => {
    // 1. Visit root page - initial load should show adult onboarding
    await page.goto("/");
    await expect(page.getByText("Little English Buddy")).toBeVisible();
    await expect(page.getByText("Grown-Up Setup & Onboarding")).toBeVisible();
    await expect(page.getByText("AI-Generated Content")).toBeVisible();
    await expect(page.getByText("Reading Support")).toBeVisible();

    // 2. Try submitting without supervision checkbox -> blocked
    const startBtn = page.getByRole("button", { name: /Start Learning/i });
    await startBtn.click();
    await expect(page.getByText(/Please confirm that an adult will supervise/i)).toBeVisible();

    // 3. Fill nickname and acknowledge
    await page.getByLabel(/Child's First Name or Nickname/i).fill("Toby");
    await page.getByLabel(/I am a parent or adult supervisor/i).check();

    // 4. Start chat directly at L1
    await page.getByRole("button", { name: /Start Learning with Pip/i }).click();

    // 5. Chat screen should be visible
    await expect(page.getByRole("heading", { name: "Little English Buddy" })).toBeVisible();
    await expect(page.getByText("Toby", { exact: true })).toBeVisible();
    await expect(page.getByText(/Level 1 Explorer/i)).toBeVisible();

    // 6. Check persistent dock buttons (touch targets at least 44px)
    const dock = page.getByRole("navigation", { name: "Learning activities" });
    const learnBtn = dock.getByRole("button", { name: "Learn" });
    const chatBtn = dock.getByRole("button", { name: "Chat" });
    const playBtn = dock.getByRole("button", { name: "Play" });
    const breakBtn = dock.getByRole("button", { name: "Break" });

    await expect(learnBtn).toBeVisible();
    await expect(chatBtn).toBeVisible();
    await expect(playBtn).toBeVisible();
    await expect(breakBtn).toBeVisible();

    const learnBox = await learnBtn.boundingBox();
    expect(learnBox?.height).toBeGreaterThanOrEqual(44);

    // 7. Click Learn button -> starts an activity
    await learnBtn.click();
    await expect(page.getByText(/Challenge 🎯/i)).toBeVisible({ timeout: 5000 });

    // 8. Type in text box and send via Enter/Send
    const input = page.getByLabel(/Type a message to Pip/i);
    await input.fill("Hello Pip, I love apples");
    await page.getByRole("button", { name: "Send" }).click();

    await expect(page.getByText("Hello Pip, I love apples", { exact: true })).toBeVisible();

    // 9. Click Break -> switches to support/break mood
    await breakBtn.click();
    await expect(page.getByText("Take a break ☕", { exact: true })).toBeVisible();

    // 10. Open Grown-Up Settings
    await page.getByLabel("Open Grown-Up Settings").click();
    await expect(page.getByText("Parental Gate")).toBeVisible();

    // Solve parental gate math (7 + 8 = 15)
    await page.getByLabel(/What is 7 \+ 8\?/i).fill("15");
    await page.getByRole("button", { name: /Unlock Settings/i }).click();

    // Check settings unlocked
    await expect(page.getByText("Current Profile Info")).toBeVisible();
    await expect(page.getByText("Local SQLite Storage")).toBeVisible();

    // Close settings
    await page.getByLabel("Close settings").click();
  });

  test("responsive layout: no horizontal overflow at 360px width", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await page.goto("/");

    // Verify page fits within 360px without scrollWidth exceeding clientWidth
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });
});
