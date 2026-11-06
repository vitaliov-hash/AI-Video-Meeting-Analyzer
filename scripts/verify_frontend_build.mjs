import assert from 'node:assert/strict';
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = resolve(import.meta.dirname, '..');
const build = resolve(root, 'scripts/build_frontend.mjs');
const output = resolve(root, 'frontend-dist');
const staticOutput = resolve(output, 'static');
const node = process.execPath;

let buildSequence = 0;
async function runBuild(args, extraEnv = {}) {
  const originalArgv = process.argv;
  const originalApi = process.env.PUBLIC_API_BASE_URL;
  process.argv = [node, build, ...args];
  if (Object.hasOwn(extraEnv, 'PUBLIC_API_BASE_URL')) process.env.PUBLIC_API_BASE_URL = extraEnv.PUBLIC_API_BASE_URL;
  else delete process.env.PUBLIC_API_BASE_URL;
  try {
    await import(`${pathToFileURL(build).href}?verification=${++buildSequence}`);
    return { status: 0, stderr: '' };
  } catch (error) {
    return { status: 1, stderr: error.message };
  } finally {
    process.argv = originalArgv;
    if (originalApi === undefined) delete process.env.PUBLIC_API_BASE_URL;
    else process.env.PUBLIC_API_BASE_URL = originalApi;
  }
}

function config() {
  const source = readFileSync(resolve(staticOutput, 'runtime-config.js'), 'utf8');
  const match = source.match(/^window\.APP_CONFIG = (.+);$/m);
  assert.ok(match, 'runtime config is valid JavaScript assignment');
  return JSON.parse(match[1]);
}

rmSync(output, { recursive: true, force: true });
mkdirSync(staticOutput, { recursive: true });
writeFileSync(resolve(staticOutput, 'stale-secret.txt'), 'must not survive a rebuild');

let result = await runBuild([], { PUBLIC_API_BASE_URL: 'https://api.example.invalid' });
assert.equal(result.status, 0, result.stderr || result.error?.message || result.stdout || 'build process did not return an exit code');
assert.deepEqual(config(), { apiBaseUrl: 'https://api.example.invalid', mode: 'live' });
assert.equal(existsSync(resolve(staticOutput, 'demo-data.json')), false, 'live build excludes showcase-only data');

result = await runBuild(['--showcase']);
assert.equal(result.status, 0, result.stderr || result.error?.message || result.stdout || 'build process did not return an exit code');
assert.deepEqual(config(), { apiBaseUrl: '', mode: 'showcase' });
assert.equal(existsSync(resolve(staticOutput, 'stale-secret.txt')), false, 'build removes stale artifacts');
assert.equal(existsSync(resolve(staticOutput, 'demo-data.json')), true, 'showcase build includes prepared examples');
const demoJson = readFileSync(resolve(staticOutput, 'demo-data.json'), 'utf8');
assert.doesNotMatch(demoJson, /(https?:\/\/|drive\.google\.com|localhost|\.sqlite3|DEEPSEEK_API_KEY)/i, 'showcase data contains no private links, database paths, or keys');
assert.deepEqual(readdirSync(output).sort(), ['index.html', 'static']);
assert.deepEqual(readdirSync(staticOutput).sort(), ['app.js', 'demo-data.json', 'runtime-config.js', 'showcase.css', 'showcase.js', 'styles.css']);
const showcaseCss = readFileSync(resolve(staticOutput, 'showcase.css'), 'utf8');
assert.match(showcaseCss, /@media\(max-width:760px\).*html\[data-app-mode="showcase"\] \.summary-grid\{grid-template-columns:minmax\(0,1fr\)\}/, 'mobile Showcase overrides desktop grid specificity');

result = await runBuild(['--showcase'], { PUBLIC_API_BASE_URL: 'https://api.example.invalid' });
assert.notEqual(result.status, 0, 'showcase refuses a configured backend');
assert.match(result.stderr, /must not include a backend API URL/);

// Leave the Vercel deployment artifact in its intended Showcase configuration.
result = await runBuild(['--showcase']);
assert.equal(result.status, 0, result.stderr);
console.log('Frontend build checks passed: live isolation, static Showcase contents, stale-file cleanup, and API URL rejection.');
