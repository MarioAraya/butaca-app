import { chromium } from 'playwright'

const OUT = '/Users/maaya/dev/que-ver-cine-hoy/screenshots/normandie-test'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

// Screenshot 1 — movie list
await page.goto('http://localhost:5175', { waitUntil: 'networkidle' })
await page.waitForSelector('.movie-card, [class*="card"]', { timeout: 15000 }).catch(() => {})
await page.waitForTimeout(1500)
await page.screenshot({ path: `${OUT}/01-movie-list.png`, fullPage: false })
console.log('shot 1 done')

// Screenshot 2 — click a Normandie card -> modal
let clicked = false
const cards = await page.locator('.movie-card, [class*="card"]').all()
for (const c of cards) {
  const txt = (await c.textContent()) || ''
  if (/normandie/i.test(txt)) {
    await c.click()
    clicked = true
    break
  }
}
if (!clicked && cards.length) { await cards[0].click(); clicked = true }
await page.waitForTimeout(1500)
await page.screenshot({ path: `${OUT}/02-movie-modal.png`, fullPage: false })
console.log('shot 2 done (clicked=' + clicked + ')')

// Screenshot 3 — raw API
await page.goto('http://localhost:8000/api/v1/movies', { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
await page.evaluate(() => {
  const t = document.body.innerText
  const i = t.toLowerCase().indexOf('normandie')
  if (i > 0) window.scrollTo(0, (i / t.length) * document.body.scrollHeight)
})
await page.waitForTimeout(500)
await page.screenshot({ path: `${OUT}/03-api-response.png`, fullPage: false })
console.log('shot 3 done')

await browser.close()
