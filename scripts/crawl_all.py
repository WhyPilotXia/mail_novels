#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 books JSON 爬取三本书的全部内容（正文、附带图片、封面图），各放一个目录。
输出目录: ~/Downloads/小说/{书名}/
用法: python3 crawl_all.py
"""
import json
import os
import re
import time
import urllib.request

BASE = "https://mail.ypan.hk"
DOWNLOAD_ROOT = os.path.expanduser("~/Downloads/小说")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookie.txt")

IMG_PATTERN = re.compile(r'(/novel/img/[A-Za-z0-9_.\-]+)')

# 三本书定义: (书名, book_id, 封面文件名, 章节列表[(序号, chapter_id)])
BOOKS = [
    ("李氏庄园", "book-mst34cam-jq76v1", "lishizhuangyuan_cover.png", [
        ("01", "chapter-mst34x23-lphhxu"), ("02", "chapter-mst39jhk-dds6he"),
        ("03", "chapter-mst3i53i-2y5kif"), ("04", "chapter-mst3zn7v-vncrx3"),
        ("05", "chapter-mst40jph-9c1oqp"), ("06", "chapter-mst44vvj-44ns1t"),
        ("07", "chapter-mst45o57-82lhqo"), ("08", "chapter-mst6duom-ispxnp"),
        ("09", "chapter-mst8aogo-5zcq1u"), ("10", "chapter-mst8iqfp-i9aq3u"),
        ("11", "chapter-mst8zqth-fd51cy"), ("12", "chapter-msu41wxv-2rydbn"),
        ("13", "chapter-msu4fxza-pwnovi"), ("14", "chapter-msu4uxgz-czojja"),
        ("15", "chapter-msujpn2k-b5sohc"), ("16", "chapter-msukeq9l-obt5p7"),
        ("17", "chapter-msunhf6h-z5dhdd"), ("18", "chapter-msuocmme-525zew"),
        ("19", "chapter-msuou1e2-8hwg1w"), ("20", "chapter-msup2nhv-vkdf5s"),
        ("21", "chapter-msuptylb-u2oquq"), ("22", "chapter-msuqjyys-93fmlq"),
        ("23", "chapter-msvng0wt-q31q02"), ("24", "chapter-msvvmadn-ljy7d6"),
        ("25", "chapter-msvvozyj-qpql4g"), ("26", "chapter-msvvwu6c-ebjlfq"),
        ("27", "chapter-msvw4wb4-lus8im"), ("28", "chapter-msvzkh92-oayo0t"),
        ("29", "chapter-msvzuvyo-v81rmx"), ("30", "chapter-msw0e0dj-k18k91"),
        ("31", "chapter-msx2606n-tdcx9s"), ("32", "chapter-msxb676u-0ptv0z"),
        ("33", "chapter-msxbvp5o-pm9frw"), ("34", "chapter-msxc8us7-258o93"),
        ("35", "chapter-msyg5l8a-goseco"), ("36", "chapter-mtem862t-o2um4c"),
        ("37", "chapter-mtemlb15-2nmowu"), ("38", "chapter-mtemw059-kq7tlm"),
        ("39", "chapter-mtkcfdg6-jtobng"),
    ]),
    ("回信券风暴", "book-mst71ql5-sstw6p", "17342.png", [
        ("01", "chapter-mst72iw7-fdgykb"), ("02", "chapter-mst759r4-j4g8tg"),
        ("03", "chapter-mst7aeig-bp5pw5"), ("04", "chapter-mst7dgas-fhrr6w"),
    ]),
    ("股神牛久盛", "book-mszmyrxu-zfsccx", "17781.png", [
        ("01", "chapter-msznhiy7-7pydub"), ("02", "chapter-mszupl4w-is0j7m"),
        ("03", "chapter-mszxg10n-hadki4"), ("04", "chapter-mszxygmj-sl87ai"),
        ("05", "chapter-mszyzli7-06ynpr"), ("06", "chapter-mszzho5x-0fgwrp"),
        ("07", "chapter-mt0007c3-rwbp04"),
    ]),
]


def load_cookie():
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def fetch_chapter(cookie, book_id, chapter_id):
    url = f"{BASE}/novel/text/books/{book_id}/chapters/{chapter_id}"
    req = urllib.request.Request(url)
    req.add_header("accept", "*/*")
    req.add_header("referer", f"https://mail.ypan.hk/novel?book={book_id}&chapter={chapter_id}")
    req.add_header("user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")
    req.add_header("cookie", cookie)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(cookie, url, dest):
    req = urllib.request.Request(url)
    req.add_header("accept", "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8")
    req.add_header("referer", f"https://mail.ypan.hk/novel?book={BOOK_REF}")
    req.add_header("user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")
    req.add_header("cookie", cookie)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        head = data[:128].lstrip().lower()
        if head.startswith(b'<!doctype') or head.startswith(b'<html') or head.startswith(b'<!'):
            raise RuntimeError("response is HTML page, not a file")
        with open(dest, "wb") as f:
            f.write(data)
    return len(data)


BOOK_REF = "book-mst34cam-jq76v1"  # 默认引用，下载时按实际书更新


def process_book(cookie, name, book_id, cover_fname, chapters):
    global BOOK_REF
    BOOK_REF = book_id

    book_dir = os.path.join(DOWNLOAD_ROOT, name)
    assets_dir = os.path.join(book_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    # 1) 封面
    cover_dest = os.path.join(assets_dir, cover_fname)
    cover_url = f"{BASE}/novel/img/{cover_fname}"
    if not os.path.exists(cover_dest):
        try:
            n = download_file(cookie, cover_url, cover_dest)
            print(f"  [封面] {name} -> {cover_dest} ({n} bytes)")
        except Exception as e:
            print(f"  [封面失败] {name} {cover_fname}: {e}")
    else:
        print(f"  [封面] 已存在，跳过")

    # 2) 逐章正文 + 图片
    merged_lines = []
    seen = set()
    for num, cid in chapters:
        try:
            data = fetch_chapter(cookie, book_id, cid)
        except Exception as e:
            print(f"  [章节失败] {num} {cid}: {e}")
            continue

        title = data.get("title", f"第 {num} 章")
        content = data.get("content", "")

        # 提取并下载图片
        md_imgs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', content)
        raw_imgs = IMG_PATTERN.findall(content)
        all_imgs = set(md_imgs + raw_imgs)
        for img_path in all_imgs:
            medium = img_path if img_path.startswith("http") else f"{BASE}{img_path}"
            fname = img_path.split("/")[-1]
            dest = os.path.join(assets_dir, fname)
            if fname in seen:
                continue
            try:
                n = download_file(cookie, medium, dest)
                seen.add(fname)
                print(f"  [图] {num} {fname} ({n} bytes)")
            except Exception as e:
                print(f"  [图失败] {num} {fname}: {e}")

# 处理正文：保留原 Markdown 图片标记，仅把图片路径改为本地 assets 相对路径
        lines = []
        for ln in content.split("\n"):
            s = ln.strip()
            if s.startswith("![") and "](" in s:
                # ![alt](/novel/img/xxx.png) -> ![alt](assets/xxx.png)
                new_ln = re.sub(r'\]\(/novel/img/([^)]+)\)', r'](assets/\1)', s)
                lines.append(new_ln)
                continue
            if s.startswith("```"):
                continue
            lines.append(ln)
        body = "\n".join(lines).strip()
        merged_lines.append(f"## {title}\n\n{body}\n")
        print(f"  [正文OK] {title}")

        # 4) 写单章 txt（含本地图片引用）
        single_path = os.path.join(book_dir, f"{num}_chapter.txt")
        with open(single_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n{body}\n")
        time.sleep(0.3)

    # 3) 合并全集
    merged_path = os.path.join(book_dir, f"{name}_全集.txt")
    with open(merged_path, "w", encoding="utf-8") as f:
        f.write(f"{name}\n" + "=" * 30 + "\n\n" + "\n".join(merged_lines))
    print(f"  [全集] -> {merged_path} ({os.path.getsize(merged_path)} bytes, {len(merged_lines)} 章)")
    print(f"  目录: {book_dir}")


def main():
    import sys
    args = sys.argv[1:]
    if args and args[0] == "--list":
        print("可用书名：")
        for name, *_ in BOOKS:
            print(f"  - {name}")
        return

    cookie = load_cookie()
    targets = BOOKS
    if args:
        only = args[0]
        targets = [b for b in BOOKS if b[0] == only]
        if not targets:
            print(f"未找到书名「{only}」，可用：{[b[0] for b in BOOKS]}")
            return
    for name, book_id, cover, chapters in targets:
        print(f"\n===== 开始爬取《{name}》 ({len(chapters)} 章) =====")
        process_book(cookie, name, book_id, cover, chapters)
    print("\n✅ 全部完成")


if __name__ == "__main__":
    main()