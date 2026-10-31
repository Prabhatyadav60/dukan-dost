/** One chat for everything: questions, entries, bill photos with paid/due, shelf history. */
import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';

const fixture = (f: string) => path.resolve('e2e/fixtures', f);

async function login(page: Page) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Login karein' }).click();
  await expect(page.getByText('Aaj ka hisaab')).toBeVisible();
}

async function ask(page: Page, text: string) {
  const box = page.getByRole('textbox', { name: /Likhein ya poochhein/ });
  await box.fill(text);
  await page.getByRole('button', { name: 'Chat mein bhejein' }).click();
}

test('chat: shop questions, off-topic refusal, entries, bill + paid/due, shelf', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await login(page);
  await page.goto('/assistant');

  await test.step('shop question is answered from shop data', async () => {
    await ask(page, 'Kis ka udhaar sabse zyada hai?');
    await expect(page.getByText('Kis ka udhaar sabse zyada hai?')).toBeVisible();
    await expect(page.locator('.bub, [class*=bub]').filter({ hasText: /Gupta ji/ }).last()).toBeVisible({ timeout: 45_000 });
  });

  await test.step('read aloud: 🔊 on an answer plays Sarvam audio', async () => {
    const answer = page.locator('.bub').filter({ hasText: /Gupta ji/ }).last();
    const audio = page.waitForResponse((r) => r.url().endsWith('/v1/tts') && r.status() === 200);
    await answer.getByRole('button', { name: 'Suno' }).click();
    const res = await audio;
    expect(res.headers()['content-type']).toContain('audio/wav');
    // the page consumes the body as a blob, so check the declared size rather than re-reading it
    expect(Number(res.headers()['content-length'])).toBeGreaterThan(10_000);
    await expect(answer.getByRole('button', { name: 'Roko' })).toBeVisible();
    await answer.getByRole('button', { name: 'Roko' }).click();
    await expect(answer.getByRole('button', { name: 'Suno' })).toBeVisible();
  });

  await test.step('off-topic question is politely declined', async () => {
    await ask(page, 'India ka cricket match kaun jeeta?');
    await expect(page.getByText(/sirf .*dukaan|dukaan ke hisaab/i).last()).toBeVisible({ timeout: 45_000 });
  });

  await test.step('an entry typed in chat still opens the confirm card', async () => {
    await ask(page, 'Verma ji 300 udhaar, chai patti');
    const sheet = page.getByRole('dialog', { name: 'Yeh sahi hai?' });
    await expect(sheet).toBeVisible({ timeout: 45_000 });
    await sheet.getByRole('button', { name: 'Haan, save karein' }).click();
    await expect(page.getByText(/Verma ji ka total ab ₹2,450/).first()).toBeVisible();
  });

  await test.step('bill photo from chat: must choose paid or due', async () => {
    await page.getByTestId('chat-photo-input').setInputFiles(fixture('balaji-bill.jpg'));
    await page.getByRole('dialog').getByRole('button', { name: 'Bill', exact: true }).click();
    await expect(page.getByText('Line items total se match karte hain')).toBeVisible({ timeout: 45_000 });
    const save = page.getByRole('button', { name: 'Kharche mein jodein' });
    await expect(save).toBeDisabled();
    await page.getByRole('radio', { name: 'Baad mein dena hai' }).click();
    await save.click();
    await expect(page.getByText(/Bill padh liya: ₹18,400, due 5 Nov/).first()).toBeVisible();
  });

  await test.step('unpaid bill shows on Forecast; marking it paid moves it out of dues', async () => {
    await page.getByRole('link', { name: 'Forecast' }).click();
    await expect(page.getByText('Balaji Traders').first()).toBeVisible();
    await page.getByRole('button', { name: 'Paid kar diya' }).first().click();
    await expect(page.getByText('Balaji Traders')).toHaveCount(0);
    await page.goto('/assistant');
    await expect(page.getByText(/paid mark kar diya/).first()).toBeVisible();
  });

  await test.step('shelf: first photo gives placement tips only', async () => {
    await page.getByRole('link', { name: 'Scan' }).click();
    await page.getByRole('tab', { name: 'Shelf' }).click();
    await page.locator('input[type=file]:not([data-testid=chat-photo-input])').setInputFiles(fixture('shelf-full.jpg'));
    await expect(page.getByText('Pehli photo — placement tips')).toBeVisible({ timeout: 45_000 });
    await page.goto('/assistant');
    await expect(page.getByText(/Pehli shelf photo save kar li/).first()).toBeVisible();
  });

  expect(errors, 'uncaught page errors').toEqual([]);
});
