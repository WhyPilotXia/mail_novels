#!/usr/bin/env python3
"""Build a credential-free Pages artifact from the current novel files.
Requires Python 3.9+ and Node.js 22+; no third-party packages or network.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
IMAGE_TYPES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif'}


def read_books(root):
    script = "const fs=require('node:fs'),vm=require('node:vm');const ctx={window:{}};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),ctx,{timeout:1000});console.log(JSON.stringify(ctx.window.BOOKS));"
    result = subprocess.run(['node', '-e', script, str(root / 'js/books.js')],
                            check=True, capture_output=True, text=True)
    books = json.loads(result.stdout)
    if not isinstance(books, list) or not books:
        raise ValueError('js/books.js must contain a non-empty BOOKS array')
    keys, dirs = set(), set()
    for book in books:
        directory = book['dir']
        if not isinstance(directory, str) or '/' in directory or '\\' in directory or directory.startswith('.'):
            raise ValueError('Invalid book directory')
        if book['key'] in keys or directory in dirs:
            raise ValueError('Duplicate book key or directory')
        keys.add(book['key'])
        dirs.add(directory)
    return books


def scan_chapters(book_dir):
    """Use actual filenames, support gaps, and reject ambiguous numeric IDs."""
    chapters, seen = [], set()
    for path in book_dir.iterdir():
        match = re.fullmatch(r'(\d+)_chapter\.txt', path.name)
        if not match:
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError('Chapter must be a regular file: ' + str(path))
        number = int(match[1])
        if number < 1 or number in seen:
            raise ValueError('Invalid or duplicate chapter number: ' + str(path))
        seen.add(number)
        with path.open(encoding='utf-8-sig') as handle:
            first_line = handle.readline().strip()
        title = re.sub(r'^#\s+', '', first_line) if first_line.startswith('# ') else '第 %s 章' % number
        chapters.append({'num': str(number).zfill(2), 'title': title,
                         'file': path.name})
    return sorted(chapters, key=lambda item: int(item['num']))


def copy_file(source, destination):
    if source.is_symlink() or not source.is_file():
        raise ValueError('Publish source must be a regular file: ' + str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def build(root=ROOT):
    root = Path(root).resolve()
    books = read_books(root)
    output = root / '_site'
    if output.is_symlink():
        raise ValueError('Refusing to follow _site symlink')
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()
    for filename in ('index.html', 'reader.html'):
        copy_file(root / filename, output / filename)
    for directory, suffix in (('js', '.js'), ('css', '.css')):
        if (root / directory).is_symlink():
            raise ValueError('Refusing symlink directory: ' + directory)
        for path in (root / directory).glob('*' + suffix):
            copy_file(path, output / path.relative_to(root))
    for book in books:
        source = root / book['dir']
        if source.is_symlink() or not source.is_dir():
            raise ValueError('Missing or unsafe novel directory: ' + str(source))
        destination = output / book['dir']
        destination.mkdir()
        chapters = scan_chapters(source)
        for chapter in chapters:
            copy_file(source / chapter['file'], destination / chapter['file'])
        (destination / 'chapters.json').write_text(
            json.dumps(chapters, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        assets = source / 'assets'
        if assets.is_symlink():
            raise ValueError('Refusing symlink assets: ' + str(assets))
        if assets.exists():
            for image in assets.rglob('*'):
                if image.is_symlink():
                    raise ValueError('Refusing symlink asset: ' + str(image))
                generated_cover = image == assets / '_cover.svg'
                if image.is_file() and (image.suffix.lower() in IMAGE_TYPES or generated_cover):
                    copy_file(image, destination / 'assets' / image.relative_to(assets))
        cover = Path(book['cover'])
        if cover.name != book['cover'] or not (destination / 'assets' / cover).is_file():
            raise ValueError('Missing or invalid cover for ' + book['dir'])
        print('%s: %d chapters' % (book['dir'], len(chapters)))
    digest = hashlib.sha256()
    for path in sorted(output.rglob('*')):
        if path.is_file():
            digest.update(path.relative_to(output).as_posix().encode())
            digest.update(path.read_bytes())
    version = digest.hexdigest()[:12]
    for filename in ('index.html', 'reader.html'):
        path = output / filename
        html = path.read_text(encoding='utf-8')
        html = re.sub(r'((?:src|href)="(?:js|css)/[^"?]+)(")',
                      lambda match: match[1] + '?v=' + version + match[2], html)
        html = html.replace('<script src=', '<script>window.SITE_VERSION=' + json.dumps(version) + ';</script>\n<script src=', 1)
        path.write_text(html, encoding='utf-8')
    (output / '.nojekyll').write_text('', encoding='utf-8')
    print('Static artifact: %s (version %s)' % (output, version))
    return output


if __name__ == '__main__':
    build()
