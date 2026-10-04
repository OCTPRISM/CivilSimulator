import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const out = '/Users/roger/Code/CivilSimulator/tmp/map-shots';
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on('console', m => { if (m.type() === 'error') console.log('ERR', m.text().slice(0, 180)); });

await page.goto('http://127.0.0.1:3000/dev/maps', { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(2000);
await page.locator('input[type="range"]').evaluate((el) => {
  el.value = '11';
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
});

const genres = [
  ['古代', '01-ancient.png'],
  ['武侠', '02-wuxia.png'],
  ['玄幻', '03-xuanhuan.png'],
  ['悬疑', '04-mystery.png'],
  ['当代', '05-modern.png'],
  ['科幻', '06-scifi.png'],
];

for (const [label, file] of genres) {
  await page.getByRole('button', { name: label, exact: true }).click();
  await page.waitForTimeout(2800);
  const canvas = page.locator('canvas').first();
  const box = await canvas.boundingBox();
  if (box) {
    await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.42);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.5, { steps: 10 });
    await page.mouse.up();
    await page.mouse.wheel(0, -700);
    await page.waitForTimeout(500);
  }
  await page.screenshot({ path: path.join(out, file), fullPage: false });
  console.log('shot', file);
}
await browser.close();
console.log('done');
