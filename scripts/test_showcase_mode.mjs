import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import vm from 'node:vm';

const root = resolve(import.meta.dirname, '..');
const demoData = JSON.parse(readFileSync(resolve(root, 'static/demo-data.json'), 'utf8'));
const appSource = readFileSync(resolve(root, 'static/app.js'), 'utf8');
const showcaseSource = readFileSync(resolve(root, 'static/showcase.js'), 'utf8');

class Element {
  constructor(id = '') { this.id = id; this._innerHTML = ''; this.cachedNodes = new Map(); this.textContent = ''; this.hidden = true; this.dataset = {}; this.listeners = {}; }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(value) { this._innerHTML = value; this.cachedNodes.clear(); }
  addEventListener(type, callback) { this.listeners[type] = callback; }
  querySelectorAll(selector) {
    if (this.cachedNodes.has(selector)) return this.cachedNodes.get(selector);
    const attr = selector === '.meeting' ? 'id' : 'variant';
    const regex = selector === '.meeting' ? /data-id="([^"]+)"/g : /data-variant="([^"]+)"/g;
    const nodes = [];
    for (const match of this.innerHTML.matchAll(regex)) {
      const node = new Element();
      node.dataset[attr] = match[1];
      node.listeners = {};
      nodes.push(node);
    }
    this.cachedNodes.set(selector, nodes);
    return nodes;
  }
}

function createHarness(saved = {}, mode = 'showcase') {
  const elements = new Map();
  const getElement = selector => {
    if (!elements.has(selector)) elements.set(selector, new Element(selector));
    return elements.get(selector);
  };
  const storage = new Map(Object.entries(saved));
  const requests = [];
  const document = { documentElement: { dataset: {} }, querySelector: getElement };
  const context = {
    document,
    window: { APP_CONFIG: { mode, apiBaseUrl: '' }, location: { search: '' }, setTimeout: () => 0 },
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, String(value)),
    },
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: true, json: async () => url === '/api/meetings' ? [] : demoData };
    },
    Intl,
    Date,
    Headers,
    URLSearchParams,
  };
  vm.runInNewContext(appSource, context, { filename: 'static/app.js' });
  vm.runInNewContext(showcaseSource, context, { filename: 'static/showcase.js' });
  return { elements, requests, storage, document };
}

const first = createHarness();
await new Promise(resolve => setTimeout(resolve, 0));
assert.deepEqual(first.requests.map(request => request.url), ['/static/demo-data.json']);
assert.match(first.elements.get('#meeting-list').innerHTML, /sample-ru-planning-01/);
assert.match(first.elements.get('#meeting-list').innerHTML, /sample-en-product-01/);
assert.match(first.elements.get('#details').innerHTML, /не ответ AI/);
assert.match(first.elements.get('#details').innerHTML, /Планирование учебного вебинара/);
assert.equal(first.document.documentElement.dataset.appMode, 'showcase');

const meetingButtons = first.elements.get('#meeting-list').querySelectorAll('.meeting');
meetingButtons[1].listeners.click();
assert.match(first.elements.get('#details').innerHTML, /Product planning session/);
assert.equal(first.storage.get('meeting-analyzer-showcase-selected'), 'sample-en-product-01');
const reviewedTab = first.elements.get('#details').querySelectorAll('.summary-tab')[1];
reviewedTab.listeners.click();
assert.equal(first.storage.get('meeting-analyzer-showcase-summary-version'), 'reviewed');
assert.match(first.elements.get('#details').innerHTML, /no production release date was set/i);
assert.equal(first.requests.some(request => String(request.url).includes('/api/')), false);

const reload = createHarness(Object.fromEntries(first.storage));
await new Promise(resolve => setTimeout(resolve, 0));
assert.match(reload.elements.get('#details').innerHTML, /Product planning session/);
assert.match(reload.elements.get('#details').innerHTML, /no production release date was set/i);
assert.deepEqual(reload.requests.map(request => request.url), ['/static/demo-data.json']);

const live = createHarness({}, 'live');
await new Promise(resolve => setTimeout(resolve, 0));
assert.deepEqual(live.requests.map(request => request.url), ['/api/meetings']);
assert.equal(typeof live.elements.get('#video-file').listeners.change, 'function', 'live mode keeps manual upload active');
assert.equal(typeof live.elements.get('#cloud-form').listeners.submit, 'function', 'live mode keeps cloud import active');
assert.notEqual(live.document.documentElement.dataset.appMode, 'showcase');

const teacher = createHarness({}, 'teacher-preview');
assert.equal(teacher.requests.length, 0, 'Teacher Preview waits for login before requesting data');
assert.equal(typeof teacher.elements.get('#teacher-login').listeners.submit, 'function', 'teacher login form is available');
assert.equal(teacher.document.documentElement.dataset.appMode, 'teacher-preview');
assert.doesNotMatch(appSource, /localStorage/i, 'teacher bearer tokens are not persisted in browser storage');
assert.match(appSource, /Authorization/);
console.log('Frontend behavior checks passed: Showcase isolation/persistence, live Lite/Pro forms, and gated Teacher Preview.');
