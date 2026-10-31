/** Home tagline, "Cash mila" (sale + udhaar repayment), today's sales drill-down, forecast cash timeline. */
import { expect, test, type Page } from '@playwright/test';

async function login(page: Page) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Login karein' }).click();
  await expect(page.getByText('Aaj ka hisaab')).toBeVisible();
}

async function addCash(page: Page, rupees: string, kind: 'Bikri' | 'Udhaar wapas', customer?: string) {
  await page.getByRole('button', { name: '+ Cash mila' }).click();
  const sheet = page.getByRole('dialog', { name: 'Cash mila' });
  await expect(sheet).toBeVisible();
  await sheet.getByRole('textbox', { name: 'Amount (₹)' }).fill(rupees);
  await sheet.getByRole('radio', { name: kind }).click();
  if (customer) {
    const select = sheet.getByRole('combobox', { name: 'Kis customer se?' });
    const value = await select.locator('option', { hasText: customer }).getAttribute('value');
    await select.selectOption(value!);
  }
  await sheet.getByRole('button', { name: 'Jod dein' }).click();
  await expect(sheet).toBeHidden();
}

test('home: tagline, cash received, sales drill-down, cash timeline', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await login(page);

  await test.step('tagline with heart', async () => {
    await expect(page.getByText('Dukan Dost · Paytm + AI, kiranas ke liye')).toBeVisible();
  });

  await test.step('sales card drills down to who paid', async () => {
    // the amount must be readable: light text on the navy card (it once inherited navy and vanished)
  await expect(page.locator('.card.dark .big').first()).toHaveCSS('color', 'rgb(246, 241, 231)');
  await page.getByRole('link', { name: 'Aaj ki bikri ka poora hisaab dekhein' }).click();
    await expect(page).toHaveURL(/\/sales$/);
    await expect(page.getByText('₹12,480').first()).toBeVisible();
    const firstPayer = page.locator('.item.payer').first();
    await expect(firstPayer).toBeVisible();
    await expect(firstPayer).not.toContainText('UPI customer');
    await page.getByRole('tab', { name: 'Sab payments' }).click();
    await expect(page.locator('.item.payment').first()).toBeVisible();
    await page.getByRole('link', { name: '← Home' }).click();
  });

  await test.step('cash sale adds to today', async () => {
    await addCash(page, '500', 'Bikri');
    await expect(page.getByText('₹500 cash bikri jod di')).toBeVisible();
    await expect(page.getByText('₹12,980')).toBeVisible();
  });

  await test.step('cash udhaar repayment reduces the balance and shows on /sales', async () => {
    await expect(page.getByText('₹8,550').first()).toBeVisible();
    await addCash(page, '300', 'Udhaar wapas', 'Verma ji');
    await expect(page.getByText('Verma ji se ₹300 mil gaye')).toBeVisible();
    await expect(page.getByText('₹8,250').first()).toBeVisible();
    await expect(page.getByText('₹12,980')).toBeVisible(); // a repayment is not a sale
    await page.getByRole('link', { name: 'Aaj ki bikri ka poora hisaab dekhein' }).click();
    const repaid = page.getByRole('region', { name: 'Aaj udhaar wapas mila' });
    await expect(repaid).toBeVisible();
    await expect(repaid).toContainText('Verma ji');
    await expect(repaid).toContainText('₹300');
  });

  await test.step('forecast shows the 30-day cash timeline', async () => {
    await page.getByRole('link', { name: 'Forecast' }).click();
    await expect(page.getByRole('region', { name: 'Agle 30 din ka paisa' })).toBeVisible({ timeout: 40_000 });
  });

  expect(errors, 'uncaught page errors').toEqual([]);
});
