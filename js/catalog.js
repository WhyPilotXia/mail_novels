// 书架和阅读器仅从构建生成的 chapters.json 获取目录，不探测章节文件。
(function () {
  'use strict';

  function assetUrl(book, path) {
    var url = encodeURIComponent(book.dir) + '/' + path.split('/').map(encodeURIComponent).join('/');
    return url + (window.SITE_VERSION ? '?v=' + encodeURIComponent(window.SITE_VERSION) : '');
  }

  async function load(book) {
    var response = await fetch(assetUrl(book, 'chapters.json'), { cache: 'no-cache' });
    if (!response.ok) throw new Error('章节目录请求失败（HTTP ' + response.status + '），请刷新重试。');
    var chapters = await response.json();
    if (!Array.isArray(chapters)) throw new Error('章节目录格式错误，请重新构建站点。');
    var seen = new Set();
    return chapters.map(function (item) {
      if (!item || !/^\d+$/.test(String(item.num)) || typeof item.title !== 'string') {
        throw new Error('章节目录条目无效，请重新构建站点。');
      }
      var num = String(item.num).padStart(2, '0');
      var file = item.file || num + '_chapter.txt';
      if (!/^\d+_chapter\.txt$/.test(file) || Number(file.split('_')[0]) !== Number(num) || seen.has(Number(num))) {
        throw new Error('章节文件名或编号无效，请重新构建站点。');
      }
      seen.add(Number(num));
      return { num: num, title: item.title, file: file };
    });
  }

  window.NovelCatalog = { load: load, assetUrl: assetUrl };
})();
