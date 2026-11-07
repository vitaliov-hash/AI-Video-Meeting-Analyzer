import { cpSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const source = resolve(root, 'static');
const output = resolve(root, 'frontend-dist');
const staticOutput = resolve(output, 'static');
const configuredApi = (process.env.PUBLIC_API_BASE_URL || '').trim().replace(/\/+$/, '');
const args = process.argv.slice(2);
const explicitShowcase = args.includes('--showcase');
const teacherFlag = args.includes('--teacher-preview');
const vercelBuild = args.includes('--vercel');
if (args.some(arg => !['--showcase', '--teacher-preview', '--vercel'].includes(arg))
    || [explicitShowcase, teacherFlag, vercelBuild].filter(Boolean).length > 1) {
  throw new Error('Choose one valid build mode: --showcase, --teacher-preview, or --vercel.');
}
const teacherPreview = teacherFlag || (vercelBuild
  && process.env.VERCEL_ENV === 'preview'
  && process.env.TEACHER_PREVIEW_BUILD === '1');
const showcase = explicitShowcase || (vercelBuild && !teacherPreview);
const mode = teacherPreview ? 'teacher-preview' : showcase ? 'showcase' : 'live';

if (showcase && configuredApi) {
  throw new Error('Showcase builds must not include a backend API URL.');
}

if (teacherPreview && (!configuredApi || !configuredApi.startsWith('https://'))) {
  throw new Error('Teacher Preview requires PUBLIC_API_BASE_URL with a public HTTPS backend origin.');
}

if (configuredApi) {
  const parsed = new URL(configuredApi);
  const isLocal = ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password
      || parsed.search || parsed.hash || (parsed.protocol !== 'https:' && !isLocal)
      || (teacherPreview && isLocal)) {
    throw new Error('PUBLIC_API_BASE_URL must be a public HTTPS origin (local HTTP is allowed for development).');
  }
}

if (vercelBuild && !showcase && !teacherPreview) {
  throw new Error('Vercel live builds are disabled; use a guarded Teacher Preview build.');
}

// Recreate generated output so stale artifacts cannot leak into Showcase.
rmSync(output, { recursive: true, force: true });
mkdirSync(staticOutput, { recursive: true });
cpSync(resolve(source, 'index.html'), resolve(output, 'index.html'));
for (const name of ['i18n.js', 'app.js', 'showcase.js', 'styles.css', 'showcase.css']) {
  cpSync(resolve(source, name), resolve(staticOutput, name));
}
if (showcase) {
  cpSync(resolve(source, 'demo-data.json'), resolve(staticOutput, 'demo-data.json'));
}
writeFileSync(
  resolve(staticOutput, 'runtime-config.js'),
  `window.APP_CONFIG = ${JSON.stringify({ apiBaseUrl: configuredApi, mode })};\n${mode !== 'live' ? `document.documentElement.dataset.appMode = '${mode}';\n` : ''}`,
  'utf8',
);
console.log(`Frontend built to ${output}; mode ${mode}; API base ${configuredApi ? 'configured' : 'same-origin'}.`);
