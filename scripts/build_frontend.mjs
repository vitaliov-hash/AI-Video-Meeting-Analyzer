import { cpSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const source = resolve(root, 'static');
const output = resolve(root, 'frontend-dist');
const staticOutput = resolve(output, 'static');
const configuredApi = (process.env.PUBLIC_API_BASE_URL || '').trim().replace(/\/+$/, '');

if (configuredApi) {
  const parsed = new URL(configuredApi);
  const isLocal = ['localhost', '127.0.0.1'].includes(parsed.hostname);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password
      || parsed.search || parsed.hash || (parsed.protocol !== 'https:' && !isLocal)) {
    throw new Error('PUBLIC_API_BASE_URL must be a public HTTPS origin (local HTTP is allowed for development).');
  }
}

mkdirSync(staticOutput, { recursive: true });
cpSync(resolve(source, 'index.html'), resolve(output, 'index.html'));
for (const name of ['app.js', 'styles.css']) {
  cpSync(resolve(source, name), resolve(staticOutput, name));
}
writeFileSync(
  resolve(staticOutput, 'runtime-config.js'),
  `window.APP_CONFIG = ${JSON.stringify({ apiBaseUrl: configuredApi })};\n`,
  'utf8',
);
console.log(`Frontend built to ${output}; API base ${configuredApi ? 'configured' : 'same-origin'}.`);
