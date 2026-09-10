// 书架页：读取 js/books.js 的书籍清单，渲染卡片。封面直接引用原始 assets 文件。
(function () {
  'use strict';
  var BOOKS = window.BOOKS || [];
  var shelf = document.getElementById('shelf');

  if (!BOOKS.length) {
    shelf.insertAdjacentHTML('beforeend',
      '<div class="placeholder">未找到书籍配置 (js/books.js)</div>');
    return;
  }

  // 轻量探测章节数：从 01_chapter.txt 递增直到 404
  async function probeCount(book) {
    var n = 1;
    while (n <= 999) {
      var url = book.dir + '/' + String(n).padStart(2, '0') + '_chapter.txt';
      var ok = false;
      try {
        var r = await fetch(url, { method: 'HEAD', cache: 'no-cache' });
        ok = r.ok;
      } catch (e) { ok = false; }
      if (!ok) break;
      n++;
    }
    return n - 1;
  }

  BOOKS.forEach(function (book, idx) {
    var card = document.createElement('article');
    card.className = 'book-card';
    var coverUrl = book.dir + '/assets/' + book.cover;
    card.innerHTML =
      '<div class="cover" style="background-image:url(&quot;' + coverUrl + '&quot;)"></div>' +
      '<div class="book-body">' +
        '<span class="book-meta">… 章</span>' +
        '<h2 class="book-title"></h2>' +
        '<p class="book-intro"></p>' +
      '</div>';
    card.querySelector('.book-title').textContent = book.slug;
    card.querySelector('.book-intro').textContent = book.intro;
    card.addEventListener('click', function () {
      try { localStorage.setItem('shelf_last_book', idx + ''); } catch (e) {}
      window.location.href = 'reader.html?book=' + encodeURIComponent(book.key);
    });
    shelf.appendChild(card);

    // 异步探测章节数并回填（若支持 HEAD）
    probeCount(book).then(function (cnt) {
      var meta = card.querySelector('.book-meta');
      if (cnt > 0) meta.textContent = cnt + ' 章';
      else meta.textContent = '点击阅读';
    });
  });
})();