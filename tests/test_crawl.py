import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import crawl_all as crawl
import build_site


def remote_book(title='新书', chapters=1):
    return {'id': 'book-new', 'title': title, 'coverUrl': '', 'description': '简介',
            'chapters': [{'id': 'ch-' + str(n), 'title': '第 %s 章' % n} for n in range(1, chapters + 1)]}


class FakeClient:
    def __init__(self, fail_image=False):
        self.fail_image = fail_image
        self.images = []

    def json(self, path):
        return {'id': path.split('/')[-1], 'title': '第 1 章',
                'content': '\n\n![正文](/novel/img/22834.jpg)\n\n'}

    def image(self, url):
        self.images.append(url)
        if self.fail_image:
            raise crawl.CrawlError('图片失败')
        return b'image-fixture'


class CrawlTest(unittest.TestCase):
    def test_catalog_dynamic_and_validation(self):
        books = crawl.validate_catalog({'books': [remote_book(chapters=101)]})
        self.assertEqual(len(books[0]['chapters']), 101)
        self.assertEqual(books[0]['chapters'][-1]['num'], '101')
        for invalid in ({}, {'books': 'html'}, {'books': [remote_book(), remote_book()]}):
            with self.assertRaises(crawl.CrawlError):
                crawl.validate_catalog(invalid)

    def test_existing_links_and_new_keys(self):
        book = crawl.validate_catalog({'books': [remote_book('李氏庄园')]})[0]
        old = {'key': 'lishizhuangyuan', 'dir': '李氏庄园', 'slug': '李氏庄园', 'cover': 'a.png'}
        entry = crawl.book_entry(book, [old])
        self.assertEqual(entry['key'], old['key'])
        self.assertEqual(entry['dir'], old['dir'])
        self.assertEqual(entry['sourceId'], 'book-new')
        renamed = dict(book, title='改名')
        self.assertEqual(crawl.book_entry(renamed, [entry])['dir'], old['dir'])
        new = crawl.book_entry(dict(book, title='../危险/名字'), [])
        self.assertNotIn('/', new['dir'])
        self.assertFalse(new['dir'].startswith('.'))
        self.assertEqual(new['cover'], '_cover.svg')

    @patch.object(crawl.time, 'sleep')
    def test_image_only_chapter_and_generated_cover_build(self, _):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            book = crawl.validate_catalog({'books': [remote_book()]})[0]
            entry = crawl.book_entry(book, [])
            client = FakeClient()
            crawl.sync_book(client, book, entry, root)
            novel = root / entry['dir']
            self.assertIn('![正文](assets/22834.jpg)', (novel / '01_chapter.txt').read_text())
            self.assertTrue((novel / 'assets/_cover.svg').is_file())
            self.assertTrue((novel / 'assets/22834.jpg').is_file())
            self.assertEqual(len(client.images), 1)
            crawl.sync_book(client, book, entry, root)
            self.assertEqual(len(client.images), 1)
            (root / 'js').mkdir()
            (root / 'css').mkdir()
            crawl.save_entries(root, [entry])
            for name in ('index.html', 'reader.html'):
                (root / name).write_text('<script src="js/books.js"></script>')
            output = build_site.build(root)
            self.assertTrue((output / entry['dir'] / 'assets/_cover.svg').is_file())
            self.assertEqual(len(json.loads((output / entry['dir'] / 'chapters.json').read_text())), 1)

    @patch.object(crawl.time, 'sleep')
    def test_failure_preserves_old_files_and_removal_is_archived(self, _):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            book = crawl.validate_catalog({'books': [remote_book()]})[0]
            entry = crawl.book_entry(book, [])
            novel = root / entry['dir']
            novel.mkdir()
            (novel / '01_chapter.txt').write_text('old text')
            (novel / '02_chapter.txt').write_text('removed text')
            (novel / 'chapters.json').write_text('old catalog')
            with self.assertRaises(crawl.CrawlError):
                crawl.sync_book(FakeClient(True), book, entry, root)
            self.assertEqual((novel / '01_chapter.txt').read_text(), 'old text')
            self.assertEqual((novel / 'chapters.json').read_text(), 'old catalog')
            self.assertTrue((novel / '02_chapter.txt').exists())
            crawl.sync_book(FakeClient(), book, entry, root)
            self.assertFalse((novel / '02_chapter.txt').exists())
            backup = list((root / '.crawl-backups').rglob('02_chapter.txt'))
            self.assertEqual(len(backup), 1)
            self.assertEqual(backup[0].read_text(), 'removed text')

    def test_credentials_not_sent_to_external_images_or_redirects(self):
        for url in ('https://example.com/img.png', '//example.com/x.png', '/novel/img/../cookie.txt', '/novel/img/%2fetc.png'):
            with self.assertRaises(crawl.CrawlError):
                crawl.image_location(url)
        with self.assertRaises(crawl.CrawlError):
            crawl.Client('fixture').request('https://example.com/')
        with self.assertRaises(crawl.CrawlError):
            crawl.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com/')
        self.assertIn('&lt;', crawl.placeholder_cover('<unsafe>'))


if __name__ == '__main__':
    unittest.main()
