/**
 * Full demo flow (build map §17) plus the side flows, against a freshly seeded API.
 * Run: API + web up, then `npx playwright test`.
 */
import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';

const fixture = (f: string) => path.resolve('e2e/fixtures', f);

async function login(page: Page) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Login karein' }).click();
  await expect(page.getByText('Aaj ka hisaab')).toBeVisible();
}

/** Types an entry the way the merchant would: the chat's own text box when in chat, else the tab-bar keyboard. */
async function typeEntry(page: Page, text: string) {
  if (page.url().endsWith('/assistant')) {
    await page.getByRole('textbox', { name: /Likhein ya poochhein/ }).fill(text);
    await page.getByRole('button', { name: 'Chat mein bhejein' }).click();
  } else {
    await page.getByRole('button', { name: 'Likh kar bhejein' }).click();
    await page.getByPlaceholder('Likhein: Sharma ji 450 udhaar').fill(text);
    await page.getByRole('button', { name: 'Bhejein', exact: true }).click();
  }
  await expect(page.getByRole('dialog', { name: 'Yeh sahi hai?' })).toBeVisible();
}

async function saveSheet(page: Page) {
  const sheet = page.getByRole('dialog', { name: 'Yeh sahi hai?' });
  await sheet.getByRole('button', { name: 'Haan, save karein' }).click();
  await expect(sheet).toBeHidden();
}

test('demo script end to end', async ({ page, context }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  // never actually leave for WhatsApp
  await context.route('https://wa.me/**', (r) => r.fulfill({ body: 'whatsapp stub' }));

  await test.step('1. login → home numbers', async () => {
    await login(page);
    await expect(page.getByText('₹12,480')).toBeVisible();
    await expect(page.getByText(/aapne bataya/)).toBeVisible();
    await expect(page.getByText('₹8,550').first()).toBeVisible();
    await expect(page.getByText(/kam padega/)).toHaveCount(0);
  });

  await test.step('2. hold mic, speak, confirm', async () => {
    const mic = page.getByRole('button', { name: 'Bolne ke liye dabaakar rakhein' });
    const box = (await mic.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.waitForTimeout(5000);
    await page.mouse.up();
    const sheet = page.getByRole('dialog', { name: 'Yeh sahi hai?' });
    await expect(sheet).toBeVisible();
    await expect(sheet.getByText('matched')).toBeVisible();
    await expect(sheet.locator('input').first()).toHaveValue('450');
    await expect(sheet.getByText('Sharma ji ka naya total: ₹1,250')).toBeVisible();
    await saveSheet(page);
    await expect(page).toHaveURL(/\/assistant$/);
    await expect(page.getByText('Likh diya. Sharma ji ka total ab ₹1,250.').first()).toBeVisible();
  });

  await test.step('3. scan the Balaji bill', async () => {
    await page.getByRole('link', { name: 'Scan' }).click();
    await page.locator('input[type=file]:not([data-testid=chat-photo-input])').setInputFiles(fixture('balaji-bill.jpg'));
    await expect(page.getByText('Line items total se match karte hain')).toBeVisible();
    await expect(page.getByText(/18,400/).first()).toBeVisible();
    await page.getByRole('radio', { name: 'Baad mein dena hai' }).click();
    await page.getByRole('button', { name: 'Kharche mein jodein' }).click();
    await expect(page.getByText(/Bill save ho gaya|Bill padh liya/).first()).toBeVisible();
  });

  await test.step('4. home alert + forecast numbers', async () => {
    await page.getByRole('link', { name: 'Home' }).click();
    await expect(page.getByText('4 Nov tak ₹15,000 kam padega')).toBeVisible();
    await expect(page.getByText('₹9,000').first()).toBeVisible();
    await page.getByRole('link', { name: 'Forecast' }).click();
    for (const amt of ['₹45,000', '₹30,000', '₹15,000', '₹9,000', '₹6,000']) {
      await expect(page.getByText(amt).first()).toBeVisible();
    }
    await expect(page.getByText('Subject to lender approval').first()).toBeVisible();
  });

  let payUrl = '';
  await test.step('5. plan reminders, send to Sharma ji', async () => {
    await page.getByRole('link', { name: 'Udhaar' }).click();
    await expect(page.getByText('Usually pays late')).toBeVisible();
    await page.getByRole('button', { name: 'Sabko reminder plan karein' }).click();
    await expect(page.getByText(/Draft for Sharma ji/)).toBeVisible();
    const card = page.locator('li, .card, .p-item, div').filter({ hasText: /Draft for Sharma ji/ }).last();
    const link = card.getByRole('link', { name: 'Pay link kholein' });
    payUrl = (await link.getAttribute('href'))!;
    expect(payUrl).toMatch(/\/pay\/[\w-]{20,}$/);
    const popup = context.waitForEvent('page');
    await card.getByRole('button', { name: 'WhatsApp par bhejein' }).click();
    const wa = await popup;
    await expect.poll(() => wa.url()).toContain('wa.me/919000000011');
    expect(decodeURIComponent(wa.url())).toContain('₹1,250');
    await wa.close();
    await expect(card.getByText('Bhej diya')).toBeVisible();
  });

  await test.step('6. customer pays from the link; merchant sees it live', async () => {
    const cust = await context.newPage();
    await cust.goto(payUrl);
    await expect(cust.getByText('Sharma ji, aapka baaki')).toBeVisible();
    await cust.getByRole('button', { name: 'Pay ₹1,250' }).click();
    await expect(cust.getByText(/paid|pay ho gaya|Dhanyavaad/i).first()).toBeVisible();
    await cust.reload();
    await expect(cust.getByRole('button', { name: /^Pay ₹/ })).toHaveCount(0);
    await cust.close();
    await expect(page.getByText('Udhaar · ₹7,750')).toBeVisible({ timeout: 15_000 });
  });

  await test.step('7. loan offer interest', async () => {
    await page.getByRole('link', { name: 'Forecast' }).click();
    await expect(page.getByText('₹13,750').first()).toBeVisible();
    await page.getByRole('button', { name: 'Loan offer dekhein' }).click();
    await expect(page.getByText('Interest darj ho gaya. Lender aapse sampark karega.')).toBeVisible();
  });

  await test.step('8. thread shows the whole story', async () => {
    await page.goto('/assistant');
    await expect(page.getByText('Sharma ji ne ₹1,250 pay kar diye.')).toBeVisible();
    await expect(page.getByText(/Bill padh liya: ₹18,400/)).toBeVisible();
    await expect(page.getByText(/₹15,000/).first()).toBeVisible();
  });

  expect(errors, 'uncaught page errors').toEqual([]);
});

test('side flows: other intents, new customer, customer page', async ({ page }) => {
  await login(page);

  await test.step('payment intent', async () => {
    await typeEntry(page, 'Gupta ji ne 500 diye');
    const sheet = page.getByRole('dialog', { name: 'Yeh sahi hai?' });
    await expect(sheet.locator('select').first()).toHaveValue('payment');
    await saveSheet(page);
    await expect(page.getByText(/Gupta ji se ₹500 mil gaye/).first()).toBeVisible();
  });

  await test.step('cash sale intent replaces today’s cash', async () => {
    await typeEntry(page, 'aaj cash 4000 aaya');
    await expect(page.getByRole('dialog').locator('select').first()).toHaveValue('cash_sale');
    await saveSheet(page);
    await page.getByRole('link', { name: 'Home' }).click();
    await expect(page.getByText('₹12,900')).toBeVisible();
  });

  await test.step('expense intent', async () => {
    await typeEntry(page, 'dukaan ka rent 8000 diya');
    const sheet = page.getByRole('dialog', { name: 'Yeh sahi hai?' });
    await expect(sheet.locator('select').first()).toHaveValue('expense');
    await expect(sheet.getByRole('radio', { name: 'Paid kar diya' })).toHaveAttribute('aria-checked', 'true');
    await saveSheet(page);
    await expect(page.getByText(/Kharcha likh diya/).first()).toBeVisible();
  });

  await test.step('unknown name → new customer form', async () => {
    await typeEntry(page, 'Ramu kaka 200 udhaar, biscuit');
    const sheet = page.getByRole('dialog', { name: 'Yeh sahi hai?' });
    await sheet.getByRole('textbox', { name: /Phone/ }).fill('+919000000099');
    await sheet.getByRole('button', { name: 'Customer jodein' }).click();
    await expect(sheet.getByText(/naya total: ₹200/)).toBeVisible();
    await saveSheet(page);
    await expect(page.getByText(/ka total ab ₹200/).first()).toBeVisible();
  });

  await test.step('customer detail: entries, do-not-remind', async () => {
    await page.getByRole('link', { name: 'Udhaar' }).click();
    await page.getByText('Anil', { exact: true }).click();
    await expect(page).toHaveURL(/\/udhaar\/\w+/);
    await expect(page.getByText('Hisaab')).toBeVisible();
    await page.getByLabel('Reminder mat bhejo').check();
    await page.goto('/udhaar');
    await expect(page.getByText('Reminder band hai').first()).toBeVisible();
  });
});
