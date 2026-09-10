const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const settle = () => new Promise(resolve => setImmediate(resolve));

class Element {
  constructor() { this.children = []; this.nodes = {}; this.style = {}; this.events = {}; this.classList = { toggle() {} }; }
  set innerHTML(value) { this.html = value; this.nodes = {}; this.children = []; }
  get innerHTML() { return this.html || ''; }
  querySelector(selector) { return this.nodes[selector] ||= new Element(); }
  appendChild(child) { this.children.push(child); }
  addEventListener(name, callback) { this.events[name] = callback; }
  click() { if (!this.disabled) this.events.click?.(); }
}
function setup(page, failCatalog = false, count = 3) {
  const elements = {};
  const requests = [];
  const document = {
    getElementById: id => elements[id] ||= new Element(),
    createElement: () => new Element(),
    querySelectorAll: () => elements.chapList?.children || []
  };
  const chapters = [1, 2, 3].slice(0, count).map(n => ({ num: `0${n}`, title: `第 ${n} 章 标题${n}`, file: `0${n}_chapter.txt` }));
  const window = { location: { search: '?book=b0' }, scrollTo() {}, SITE_VERSION: 'test-version' };
  window.BOOKS = [0, 1, 2].map(n => ({ key: `b${n}`, dir: `书${n}`, slug: `书${n}`, cover: 'cover.png', intro: '' }));
  const storage = new Map();
  const context = vm.createContext({ window, document, URLSearchParams, console,
    localStorage: { getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v) },
    fetch: async (url, options) => {
      requests.push({ url, options });
      if (url.includes('chapters.json')) return { ok: !failCatalog, status: failCatalog ? 404 : 200, json: async () => chapters };
      return { ok: true, text: async () => '# 标题\n\n测试正文' };
    }
  });
  for (const name of ['catalog.js', page]) vm.runInContext(fs.readFileSync(path.join(root, 'js', name), 'utf8'), context);
  return { elements, requests, chapters };
}

test('shelf makes only 3 catalog requests, never chapter HEAD/GET', async () => {
  const { requests, elements } = setup('app.js');
  await settle();
  assert.equal(requests.length, 3);
  assert.ok(requests.every(r => r.url.includes('chapters.json?v=test-version')));
  assert.ok(elements.shelf.children.every(card => card.querySelector('.book-meta').textContent === '3 章'));
});
test('catalog failure on shelf never falls back to probing', async () => {
  const { requests, elements } = setup('app.js', true);
  await settle();
  assert.equal(requests.length, 3);
  assert.match(elements.shelf.children[0].querySelector('.book-meta').textContent, /失败/);
});
test('reader only requests current chapter; buttons show titles; visited chapters cached', async () => {
  const { requests, elements, chapters } = setup('reader.js');
  await settle();
  assert.equal(requests.length, 2);
  assert.match(requests[1].url, /01_chapter.txt/);
  assert.ok(elements.article.querySelector('#prevBtn').hidden);
  assert.equal(elements.article.querySelector('#nextBtn').textContent, '下一章 ' + chapters[1].title);
  elements.article.querySelector('#nextBtn').click();
  await settle();
  assert.equal(requests.length, 3);
  assert.match(requests[2].url, /02_chapter.txt/);
  assert.equal(elements.article.querySelector('#prevBtn').textContent, '上一章 ' + chapters[0].title);
  elements.article.querySelector('#prevBtn').click();
  await settle();
  assert.equal(requests.length, 3);
  elements.chapList.children[2].click();
  await settle();
  assert.equal(requests.length, 4);
  assert.ok(elements.article.querySelector('#nextBtn').hidden);
});
test('reader catalog failure makes zero chapter requests', async () => {
  const { requests, elements } = setup('reader.js', true);
  await settle();
  assert.equal(requests.length, 1);
  assert.match(elements.article.innerHTML, /失败/);
});
