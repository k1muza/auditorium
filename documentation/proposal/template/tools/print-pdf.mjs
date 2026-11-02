// Prints the proposal to PDF with zero margins and correct sheet sizes.
// Usage:  npm install  &&  npm run pdf        -> proposal-a3.pdf (A4 pages + A3 landscape sheets, mixed sizes)
//         npm run pdf:a4                       -> proposal-a4.pdf (every page A4; A3 sheets rotated and fitted)
import puppeteer from 'puppeteer';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mode = process.argv.includes('--a4') ? 'a4' : 'a3';
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp' };

const server = http.createServer((req, res) => {
  const file = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!file.startsWith(root)) { res.statusCode = 403; return res.end(); }
  fs.readFile(file, (err, buf) => {
    if (err) { res.statusCode = 404; return res.end(); }
    res.setHeader('Content-Type', types[path.extname(file).toLowerCase()] || 'application/octet-stream');
    res.end(buf);
  });
}).listen(0);
const port = server.address().port;

const browser = await puppeteer.launch();
const page = await browser.newPage();
await page.goto(`http://localhost:${port}/${encodeURIComponent('Church Auditorium Proposal.dc.html')}?sheets=${mode}`, { waitUntil: 'networkidle0' });
await page.waitForFunction(() => document.querySelectorAll('[data-page]').length >= 26 && document.body.innerText.includes('PL06'), { timeout: 30000 });
await page.evaluate(async () => {
  document.querySelectorAll('img[loading="lazy"]').forEach(i => { i.loading = 'eager'; });
  await document.fonts.ready;
  await Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; })));
});
const out = path.join(root, `proposal-${mode}.pdf`);
await page.pdf({ path: out, preferCSSPageSize: true, printBackground: true, displayHeaderFooter: false, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
await browser.close();
server.close();
console.log('Wrote', out);
