import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('build_site', Path(__file__).resolve().parents[1] / 'scripts/build_site.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildTest(unittest.TestCase):
    def test_rebuild_from_actual_files_and_exclude_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('js', 'css', 'scripts', '测试书/assets'):
                (root / folder).mkdir(parents=True, exist_ok=True)
            (root / 'js/books.js').write_text('window.BOOKS=' + json.dumps([
                {'key': 'demo', 'dir': '测试书', 'cover': 'cover.png'}]))
            for name in ('index.html', 'reader.html'):
                (root / name).write_text('<script src="js/books.js"></script>')
            book = root / '测试书'
            (book / 'assets/cover.png').write_bytes(b'test image placeholder')
            (book / 'assets/cookie.txt').write_text('not-a-real-credential')
            (root / 'scripts/cookie.txt').write_text('not-a-real-credential')
            (book / '01_chapter.txt').write_text('# 第一章\n\n正文', encoding='utf-8')
            (book / '03_chapter.txt').write_text('# 第三章\n\n正文', encoding='utf-8')
            (book / 'chapters.json').write_text('stale and invalid')
            output = builder.build(root)
            catalog = lambda: json.loads((output / '测试书/chapters.json').read_text())
            self.assertEqual([c['num'] for c in catalog()], ['01', '03'])
            self.assertFalse(list(output.rglob('cookie.txt')))
            self.assertFalse((output / 'scripts').exists())
            html = (output / 'reader.html').read_text()
            self.assertIn('SITE_VERSION', html)
            self.assertIn('?v=', html)
            (book / '01_chapter.txt').unlink()
            (book / '03_chapter.txt').write_text('# 第三章改名\n\n新正文', encoding='utf-8')
            (book / '100_chapter.txt').write_text('# 第一百章\n\n正文', encoding='utf-8')
            builder.build(root)
            self.assertEqual([c['num'] for c in catalog()], ['03', '100'])
            self.assertEqual(catalog()[0]['title'], '第三章改名')
            self.assertFalse((output / '测试书/01_chapter.txt').exists())
            self.assertNotEqual(html, (output / 'reader.html').read_text())

    def test_duplicate_numbers_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory)
            for name in ('1_chapter.txt', '01_chapter.txt'):
                (book / name).write_text('# 标题', encoding='utf-8')
            with self.assertRaises(ValueError):
                builder.scan_chapters(book)


if __name__ == '__main__':
    unittest.main()
