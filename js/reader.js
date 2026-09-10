// 阅读器：按需加载章节，解决一次性拉取所有章节导致的卡顿。
// - 章节目录：优先读取 {书名}/chapters.json（爬虫生成），缺失时回退动态探测 NN_chapter.txt。
// - 正文：仅在用户选章 / 上一章 / 下一章时异步加载当前章并内存缓存，已读章节切换不重复下载。
// - 其余功能保持：封面、内嵌图渲染、进度记忆、上下章、目录高亮。
(function () {
  'use strict';

  var BOOKS = window.BOOKS || [];

  function getQ(name) {
    return new URLSearchParams(window.location.search).get(name);
  }
  function storageKey(bookKey) { return 'novel_progress_' + bookKey; }

  async function fetchText(url) {
    var resp = await fetch(url, { cache: 'force-cache' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return resp.text();
  }

  // Range 只读文件开头若干字节，用于探测标题（GitHub Pages 支持 206）
  async function fetchHead(url, size) {
    try {
      var resp = await fetch(url, { headers: { Range: 'bytes=0-' + (size - 1) }, cache: 'force-cache' });
      if (resp.status !== 206 && resp.status !== 200) throw new Error('HTTP ' + resp.status);
      return await resp.text();
    } catch (e) { throw e; }
  }

  function parseTitle(txt) {
    var m = txt.match(/^#\s+(.+)\s*$/m);
    return m ? m[1].trim() : '章节';
  }

  // 回退方案：动态探测章节（尝试 Range 取标题；不支持则回退全量）
  async function probeChapters(book) {
    var chapters = [];
    var dir = book.dir;
    for (var n = 1; n <= 999; n++) {
      var num = String(n).padStart(2, '0');
      var url = dir + '/' + num + '_chapter.txt';
      var text = null;
      try {
        text = await fetchHead(url, 2048);
      } catch (e) {
        try { text = await fetchText(url); } catch (e2) { break; }
      }
      chapters.push({ num: num, title: parseTitle(text), loaded: false });
    }
    return chapters;
  }

  // 优先读 chapters.json；缺失则回退探测
  async function loadChapterList(book) {
    try {
      var text = await fetchText(book.dir + '/chapters.json');
      var arr = JSON.parse(text);
      if (!Array.isArray(arr) || !arr.length) throw new Error('empty');
      return arr.map(function (it) {
        return { num: String(it.num).padStart(2, '0'), title: it.title || ('第 ' + it.num + ' 章'), loaded: false };
      });
    } catch (e) {
      return await probeChapters(book);
    }
  }

  // 按需加载某章正文（内存缓存）
  var _cache = {};
  async function loadChapter(book, ch) {
    if (ch.loaded) return _cache[book.key + ':' + ch.num];
    var text = await fetchText(book.dir + '/' + ch.num + '_chapter.txt');
    _cache[book.key + ':' + ch.num] = text;
    ch.loaded = true;
    return text;
  }

  // 去除正文的标题行(第一行 # ...)，返回纯正文
  function stripTitle(txt) {
    return txt.replace(/^#\s+.*\s*$/m, '').trim();
  }

  // 把正文渲染为 HTML：内嵌图 ![alt](assets/x.png) 转 <figure><img>, 其余按段落包 <p>
  function renderBody(book, content) {
    var dir = book.dir;
    var figPattern = /!\[([^\]]*)\]\((assets\/([^)]+))\)/g;
    var figs = [];
    var body = content.replace(figPattern, function (m, alt, path, fname) {
      figs.push(
        '<figure class="novel-img"><img src="' + dir + '/assets/' + fname + '" alt="' +
        (alt || '') + '" loading="lazy">' +
        (alt ? '<figcaption>' + esc(alt) + '</figcaption>' : '') + '</figure>'
      );
      return '\u0000' + (figs.length - 1) + '\u0000';
    });

    var html = '';
    var paragraphs = body.split(/\n{2,}/);
    paragraphs.forEach(function (p) {
      p = p.trim();
      if (!p) return;
      if (/^\u0000\d+\u0000$/.test(p)) {
        html += figs[parseInt(p.replace(/\u0000/g, ''), 10)] + '\n';
        return;
      }
      var line = p.replace(/^```|```$/g, '').trim();
      if (line) html += '<p>' + esc(line).replace(/\n/g, '<br>') + '</p>';
    });
    return html;
  }

  function esc(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  var State = { book: null, chapters: [], idx: 0 };

  async function init() {
    if (!BOOKS.length) { bootError('未找到书籍配置 (js/books.js)'); return; }

    var key = getQ('book');
    if (!key) {
      try { key = BOOKS[parseInt(localStorage.getItem('shelf_last_book') || '0', 10) || 0].key; } catch (e) {}
    }
    State.book = BOOKS.find(function (b) { return b.key === key; }) || BOOKS[0];
    document.title = State.book.slug + ' · 阅读';
    renderSidebar();

    try {
      State.chapters = await loadChapterList(State.book);
    } catch (e) {
      bootError('加载章节失败：' + e.message);
      return;
    }
    if (!State.chapters.length) {
      bootError('未探测到章节，请确认目录包含 chapters.json 或 01_chapter.txt 等文件。');
      return;
    }
    buildChapterList();

    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(storageKey(State.book.key)) || 'null'); } catch (e) {}
    var startIdx = (saved && saved.idx >= 0 && saved.idx < State.chapters.length) ? saved.idx : 0;
    goTo(startIdx, false);
  }

  function renderSidebar() {
    var b = State.book;
    document.getElementById('sideCover').style.backgroundImage =
      'url("' + b.dir + '/assets/' + b.cover + '")';
    document.getElementById('sideName').textContent = b.slug;
    document.getElementById('sideDesc').textContent = b.intro;
  }

  function buildChapterList() {
    var list = document.getElementById('chapList');
    list.innerHTML = '';
    State.chapters.forEach(function (ch, i) {
      var btn = document.createElement('button');
      btn.className = 'chap-item';
      btn.type = 'button';
      btn.textContent = ch.title;
      btn.addEventListener('click', function () { goTo(i, true); });
      list.appendChild(btn);
    });
  }

  function setActive(idx) {
    var items = document.querySelectorAll('#chapList .chap-item');
    for (var i = 0; i < items.length; i++) items[i].classList.toggle('active', i === idx);
  }

  function goTo(idx, save) {
    if (idx < 0 || idx >= State.chapters.length) return;
    State.idx = idx;
    var ch = State.chapters[idx];
    var art = document.getElementById('article');
    art.innerHTML =
      '<header class="article-header"><p class="article-book"></p><h2 class="article-title"></h2></header>' +
      '<div class="prose"><p class="loading">加载中…</p></div>' +
      '<footer class="article-footer"><button class="nav-btn ghost" id="prevBtn">← 上一章</button>' +
      '<button class="nav-btn" id="nextBtn">下一章 →</button></footer>';
    art.querySelector('.article-book').textContent = State.book.slug;
    art.querySelector('.article-title').textContent = ch.title;

    var prev = art.querySelector('#prevBtn'), next = art.querySelector('#nextBtn');
    prev.disabled = idx === 0;
    prev.addEventListener('click', function () { goTo(idx - 1, true); });
    next.disabled = idx === State.chapters.length - 1;
    next.addEventListener('click', function () { goTo(idx + 1, true); });

    setActive(idx);
    if (save) { try { localStorage.setItem(storageKey(State.book.key), JSON.stringify({ idx: idx, title: ch.title })); } catch (e) {} }
    window.scrollTo({ top: 0 });

    // 按需异步加载当前章正文
    loadChapter(State.book, ch).then(function (text) {
      if (State.idx !== idx) return; // 用户已切到别的章节，忽略过期返回
      art.querySelector('.prose').innerHTML = renderBody(State.book, stripTitle(text));
    }).catch(function (e) {
      art.querySelector('.prose').innerHTML = '<p class="loading">加载失败：' + esc(e.message) + '</p>';
    });
  }

  function bootError(msg) {
    var art = document.getElementById('article');
    if (art) art.innerHTML = '<div class="placeholder">' + esc(msg) + '</div>';
  }

  document.getElementById('backBtn').addEventListener('click', function () {
    window.location.href = 'index.html';
  });

  init();
})();