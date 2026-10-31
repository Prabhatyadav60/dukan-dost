/** Asking by voice: the answer appears in chat and is read aloud automatically (Sarvam TTS). */
import { expect, test } from '@playwright/test';
import path from 'node:path';

test.use({
  launchOptions: {
    args: ['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
      `--use-file-for-fake-audio-capture=${path.resolve('e2e/fixtures/question.wav')}`],
  },
});

test('voice question → spoken answer', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Login karein' }).click();
  await expect(page.getByText('Aaj ka hisaab')).toBeVisible();

  const spoken = page.waitForResponse((r) => r.url().endsWith('/v1/tts') && r.status() === 200, { timeout: 60_000 });
  const mic = page.getByRole('button', { name: 'Bolne ke liye dabaakar rakhein' });
  const box = (await mic.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(4500);
  await page.mouse.up();

  await expect(page).toHaveURL(/\/assistant$/);
  const answer = page.locator('.bub:not(.me)').filter({ hasText: /Gupta ji/ }).last();
  await expect(answer).toBeVisible({ timeout: 45_000 });
  await expect(page.getByRole('dialog', { name: 'Yeh sahi hai?' })).toHaveCount(0); // a question, not an entry
  await spoken;
  await expect(answer.getByRole('button', { name: 'Roko' })).toBeVisible(); // auto-playing, no tap needed
});
