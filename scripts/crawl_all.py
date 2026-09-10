#!/usr/bin/env python3
"""Locally sync /novel/text to this repository, then manually commit/push.
Python 3.9+ and Node.js 22+, standard libraries only. Never run in Pages CI.
"""
import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from build_site import read_books

BASE = 'https://mail.ypan.hk'
ROOT = Path(__file__).resolve().parents[1]
COOKIE_FILE = ROOT / 'scripts/cookie.txt'
IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
ID_PATTERN = re.compile(r'[A-Za-z0-9_-]+')


class CrawlError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CrawlError('接口发生重定向，可能需要更新本地 Cookie；未转发凭据。')


def load_cookie(path=COOKIE_FILE):
    cookie = os.environ.get('MAIL_NOVEL_COOKIE', '').strip()
    if not cookie:
        try:
            cookie = Path(path).read_text(encoding='utf-8').strip()
        except FileNotFoundError:
            raise CrawlError('请在 scripts/cookie.txt 或 MAIL_NOVEL_COOKIE 中设置 Cookie。') from None
    if not cookie or '\n' in cookie or '\r' in cookie:
        raise CrawlError('Cookie 必须是非空的一行请求头内容。')
    return cookie


class Client:
    def __init__(self, cookie):
        self.cookie = cookie
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, url):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != 'mail.ypan.hk':
            raise CrawlError('只允许请求原站 HTTPS 地址，未发送 Cookie。')
        req = urllib.request.Request(url, headers={
            'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'no-cache', 'Referer': BASE + '/novel',
            'User-Agent': 'Mozilla/5.0', 'Cookie': self.cookie,
        })
        try:
            with self.opener.open(req, timeout=30) as response:
                data = response.read()
                content_type = response.headers.get_content_type()
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise CrawlError('鉴权失败，请更新本地 Cookie 后重试。') from None
            raise CrawlError('原站请求失败：HTTP %s' % error.code) from None
        except (urllib.error.URLError, TimeoutError):
            raise CrawlError('网络请求失败或超时，请稍后重试。') from None
        if content_type == 'text/html' or data.lstrip().lower().startswith((b'<!doctype', b'<html')):
            raise CrawlError('接口返回了 HTML 而非数据，请检查本地登录态。')
        return data, content_type

    def json(self, path):
        raw, _ = self.request(BASE + path)
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise CrawlError('接口未返回有效 JSON，未修改本地小说。') from None
        return data

    def image(self, url):
        raw, content_type = self.request(url)
        if not raw or not content_type.startswith('image/'):
            raise CrawlError('图片接口返回非图片数据。')
        return raw


def required_text(obj, key):
    value = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(value, str) or not value.strip() or '\n' in value or '\r' in value:
        raise CrawlError('书目或章节字段无效：' + key)
    return value.strip()


def identifier(obj):
    value = required_text(obj, 'id')
    if not ID_PATTERN.fullmatch(value):
        raise CrawlError('无效的远端 ID。')
    return value


def validate_catalog(data):
    if not isinstance(data, dict) or not isinstance(data.get('books'), list):
        raise CrawlError('书目接口应返回 {books: [...]}，未修改本地文件。')
    books, ids = [], set()
    for item in data['books']:
        book_id = identifier(item)
        if book_id in ids:
            raise CrawlError('书目存在重复 ID。')
        ids.add(book_id)
        title = required_text(item, 'title')
        chapters = item.get('chapters')
        if not isinstance(chapters, list):
            raise CrawlError('书目缺少 chapters 列表。')
        chapter_ids, normalized = set(), []
        for index, chapter in enumerate(chapters, 1):
            chapter_id = identifier(chapter)
            if chapter_id in chapter_ids:
                raise CrawlError('章节存在重复 ID。')
            chapter_ids.add(chapter_id)
            normalized.append({'id': chapter_id, 'num': str(index).zfill(2),
                               'title': required_text(chapter, 'title')})
        cover, intro = item.get('coverUrl', ''), item.get('description', '')
        if not isinstance(cover, str) or not isinstance(intro, str):
            raise CrawlError('封面或简介格式无效。')
        books.append({'id': book_id, 'title': title, 'coverUrl': cover,
                      'description': intro, 'chapters': normalized})
    return books


def image_location(value):
    url = urllib.parse.urljoin(BASE + '/', value)
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'mail.ypan.hk' or parsed.query or parsed.fragment:
        raise CrawlError('不支持外站或带参数的图片地址，未发送 Cookie。')
    filename = urllib.parse.unquote(parsed.path.removeprefix('/novel/img/'))
    if not parsed.path.startswith('/novel/img/') or not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:png|jpg|jpeg|gif|webp|avif)', filename, re.I):
        raise CrawlError('图片路径不安全或格式不支持。')
    return url, filename


def book_entry(book, entries):
    existing = next((b for b in entries if b.get('sourceId') == book['id']), None)
    if existing is None:
        existing = next((b for b in entries if b.get('slug') == book['title'] and not b.get('sourceId')), None)
    if existing:
        result = dict(existing)
    else:
        directory = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', book['title']).strip(' .') or book['id']
        if any(b['dir'].casefold() == directory.casefold() for b in entries):
            directory += '_' + book['id']
        if any(b['key'] == book['id'] for b in entries):
            raise CrawlError('新书 key 与已有书籍冲突。')
        result = {'key': book['id'], 'dir': directory, 'prefix': ''}
    result.update(sourceId=book['id'], slug=book['title'], intro=book['description'])
    result['cover'] = image_location(book['coverUrl'])[1] if book['coverUrl'] else '_cover.svg'
    return result


def placeholder_cover(title):
    title = html.escape(title)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">'
            '<rect width="600" height="800" fill="#172338"/>'
            '<rect x="30" y="30" width="540" height="740" rx="12" fill="none" stroke="#cdb486"/>'
            '<path d="M210 240h80q10 0 10 12q0-12 10-12h80v110h-80q-10 0-10 12q0-12-10-12h-80z" '
            'fill="none" stroke="#cdb486" stroke-width="4"/>'
            '<foreignObject x="60" y="420" width="480" height="220">'
            '<div xmlns="http://www.w3.org/1999/xhtml" style="color:#f6ead1;font:42px serif;text-align:center;overflow-wrap:anywhere">'
            + title + '</div></foreignObject>'
            '<text x="300" y="715" fill="#cdb486" font-size="20" text-anchor="middle">暂无封面</text></svg>')


def localize_body(client, content, stage, current, refresh=False):
    def replace(match):
        url, filename = image_location(match[2])
        ensure_image(client, url, filename, stage, current, refresh)
        return '![' + match[1] + '](assets/' + filename + ')'
    body = IMAGE_PATTERN.sub(replace, content)
    return '\n'.join(line for line in body.splitlines() if not line.strip().startswith('```')).strip()


def ensure_image(client, url, filename, stage, current, refresh):
    target = stage / 'assets' / filename
    if target.exists():
        return
    old = current / 'assets' / filename
    if old.is_symlink():
        raise CrawlError('拒绝读取符号链接图片。')
    if not refresh and old.is_file() and old.stat().st_size:
        shutil.copyfile(old, target)
    else:
        target.write_bytes(client.image(url))


def atomic_write(path, text):
    path = Path(path)
    if path.is_symlink():
        raise CrawlError('拒绝覆盖符号链接文件。')
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.crawl-', delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(text)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def sync_book(client, book, entry, root, refresh=False):
    current = root / entry['dir']
    if current.is_symlink() or (current / 'assets').is_symlink():
        raise CrawlError('拒绝写入符号链接目录。')
    with tempfile.TemporaryDirectory(prefix='.crawl-', dir=root) as temp:
        stage = Path(temp)
        (stage / 'assets').mkdir()
        if book['coverUrl']:
            url, filename = image_location(book['coverUrl'])
            ensure_image(client, url, filename, stage, current, refresh)
        else:
            (stage / 'assets/_cover.svg').write_text(placeholder_cover(book['title']), encoding='utf-8')
        metadata, merged = [], []
        for chapter in book['chapters']:
            path = '/novel/text/books/%s/chapters/%s' % (book['id'], chapter['id'])
            data = client.json(path)
            if not isinstance(data, dict) or not isinstance(data.get('content'), str):
                raise CrawlError('章节正文缺失，保留本书旧文件。')
            if data.get('id') != chapter['id']:
                raise CrawlError('章节响应 ID 不匹配，保留本书旧文件。')
            title = required_text(data, 'title')
            body = localize_body(client, data['content'], stage, current, refresh)
            filename = chapter['num'] + '_chapter.txt'
            (stage / filename).write_text('# ' + title + '\n\n' + body + '\n', encoding='utf-8')
            metadata.append({'num': chapter['num'], 'title': title, 'file': filename, 'id': chapter['id']})
            merged.append('## ' + title + '\n\n' + body + '\n')
            print('  [正文与插图] ' + title, flush=True)
            time.sleep(0.3)
        (stage / 'chapters.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (stage / (entry['dir'] + '_全集.txt')).write_text(book['title'] + '\n' + '=' * 30 + '\n\n' + '\n'.join(merged), encoding='utf-8')
        # Only touch the current book after all its chapters/images have succeeded.
        (current / 'assets').mkdir(parents=True, exist_ok=True)
        staged = [p for p in stage.rglob('*') if p.is_file()]
        if any((current / p.relative_to(stage)).is_symlink() for p in staged):
            raise CrawlError('拒绝覆盖符号链接文件。')
        keep = {c['file'] for c in metadata}
        obsolete = [p for p in current.glob('*_chapter.txt') if re.fullmatch(r'\d+_chapter\.txt', p.name) and p.name not in keep]
        if obsolete:
            backup_root = root / '.crawl-backups'
            if backup_root.is_symlink():
                raise CrawlError('拒绝写入符号链接备份目录。')
            backup_root.mkdir(exist_ok=True)
            backup = Path(tempfile.mkdtemp(prefix=book['id'] + '-', dir=backup_root))
            for path in obsolete:
                path.replace(backup / path.name)
            print('  [归档] 已移除章节保留于 .crawl-backups，不再进入构建。')
        for path in staged:
            path.replace(current / path.relative_to(stage))


def save_entries(root, entries):
    content = ('// 本地爬虫生成；旧书 key/dir 保留，新书自动登记。Pages 构建不访问原站。\n'
               'window.BOOKS = ' + json.dumps(entries, ensure_ascii=False, indent=2) + ';\n')
    atomic_write(root / 'js/books.js', content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('books', nargs='*', help='按书名或远端 ID 选择；默认所有书')
    parser.add_argument('--list', action='store_true', help='只获取远端书目，不写小说或书架')
    parser.add_argument('--refresh-images', action='store_true', help='重新下载已有图片和封面')
    parser.add_argument('--cookie-file', type=Path, default=COOKIE_FILE)
    args = parser.parse_args(argv)
    try:
        client = Client(load_cookie(args.cookie_file))
        books = validate_catalog(client.json('/novel/text'))
        if args.list:
            for book in books:
                print('%s | %s | %d 章%s' % (book['title'], book['id'], len(book['chapters']), ' | 暂无封面' if not book['coverUrl'] else ''))
            return 0
        if not books:
            raise CrawlError('远端书目为空，保留本地书架不变。')
        unknown = set(args.books) - {value for book in books for value in (book['title'], book['id'])}
        if unknown:
            raise CrawlError('找不到指定书籍：' + '、'.join(sorted(unknown)))
        targets = [b for b in books if not args.books or b['title'] in args.books or b['id'] in args.books]
        entries = read_books(ROOT)
        for book in targets:
            entry = book_entry(book, entries)
            if not any(b['dir'] == entry['dir'] for b in entries) and (ROOT / entry['dir']).exists():
                raise CrawlError('新书目录已存在但未登记，拒绝覆盖：' + entry['dir'])
            print('开始同步《%s》：%d 章' % (book['title'], len(book['chapters'])), flush=True)
            sync_book(client, book, entry, ROOT, args.refresh_images)
            index = next((i for i, b in enumerate(entries) if b['key'] == entry['key']), len(entries))
            if index == len(entries):
                entries.append(entry)
            else:
                entries[index] = entry
            save_entries(ROOT, entries)
        print('本地同步完成。请检查 git diff，构建验证后再提交推送。')
        return 0
    except (CrawlError, OSError, ValueError) as error:
        print('同步失败：' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
