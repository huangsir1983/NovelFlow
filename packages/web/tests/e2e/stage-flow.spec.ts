import { expect, test } from '@playwright/test';

test('project stage routes navigate across workbench board preview', async ({ page }) => {
  await page.goto('/zh/projects/demo/workbench');
  await expect(page.getByText('Workbench Stage')).toBeVisible();

  await page.getByRole('button', { name: 'Board' }).click();
  await expect(page).toHaveURL(/\/projects\/demo\/board$/);
  await expect(page.getByText('Board Stage')).toBeVisible();

  await page.getByRole('button', { name: 'Preview' }).click();
  await expect(page).toHaveURL(/\/projects\/demo\/preview$/);
  await expect(page.getByText('Preview Stage')).toBeVisible();
});
