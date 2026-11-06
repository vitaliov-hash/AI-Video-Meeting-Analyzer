import { cpSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const source = resolve(root, 'static');
const output = resolve(root, 'frontend-dist');
const staticOutput = resolve(output, 'static');
const configuredApi = (process.env.PUBLIC_API_BASE_URL || '').trim().replace(/\/+$/, '');
const showcase = process.argv.includes('--showcase');

if (showcase && configuredApi) {
  throw new Error('Showcase builds must not include a backend API URL.');
}

if (configuredApi) {
  const parsed = new URL(configuredApi);
  const isLocal = ['localhost', '127.0.0.1'].includes(parsed.hostname);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password
      || parsed.search || parsed.hash || (parsed.protocol !== 'https:' && !isLocal)) {
    throw new Error('PUBLIC_API_BASE_URL must be a public HTTPS origin (local HTTP is allowed for development).');
  }
}

// Recreate generated output so stale artifacts cannot leak into Showcase.
rmSync(output, { recursive: true, force: true });
mkdirSync(staticOutput, { recursive: true });
cpSync(resolve(source, 'index.html'), resolve(output, 'index.html'));
for (const name of ['app.js', 'showcase.js', 'styles.css', 'showcase.css']) {
  cpSync(resolve(source, name), resolve(staticOutput, name));
}
if (showcase) {
  cpSync(resolve(source, 'demo-data.json'), resolve(staticOutput, 'demo-data.json'));
}
writeFileSync(
  resolve(staticOutput, 'runtime-config.js'),
  `window.APP_CONFIG = ${JSON.stringify({ apiBaseUrl: configuredApi, mode: showcase ? 'showcase' : 'live' })};\n${showcase ? "document.documentElement.dataset.appMode = 'showcase';\n" : ''}`,
  'utf8',
);
console.log(`Frontend built to ${output}; mode ${showcase ? 'showcase' : 'live'}; API base ${configuredApi ? 'configured' : 'same-origin'}.`);
