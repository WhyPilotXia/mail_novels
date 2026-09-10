# 邮件小说批量爬取

自动将「Mail Web」小说平台（`mail.ypan.hk`）上的小说按本抓取为 Markdown 文本，同时下载封面与正文插图，归入本地 `~/Downloads/小说/{书名}/` 目录，方便离线阅读与归档。

本项目为自用工具，所有内容用于个人阅读备份。

---

## 目录结构

```
小说/
├── README.md              # 本说明
├── .gitignore             # Git 忽略规则（含 cookie 与输出目录）
├── scripts/               # 爬取脚本与配置
│   ├── crawl_all.py       # 主脚本：三本书正文 + 封面 + 插图 + 单章/全集
│   └── cookie.txt         # 登录凭据（勿提交到 git）
├── 李氏庄园/              # 输出：每本书一个目录
│   ├── 01_chapter.txt     # 单章（编号 + 标题）
│   ├── …
│   ├── 李氏庄园_全集.txt   # 全部章节合并
│   └── assets/            # 封面 + 正文插图
│       ├── lishizhuangyuan_cover.png
│       ├── image.png
│       ├── 22091.jpg
│       └── 22092.jpg
├── 回信券风暴/
└── 股神牛久盛/
```

---

## quick start

### 1. 安装 / 依赖

仅需 Python 3 标准库，无第三方依赖。

```bash
python3 --version   # 3.7+ 即可
```

### 2. 配置 Cookie

平台需要登录态。将浏览器中的 Cookie 复制到 `scripts/cookie.txt`（**一行**，无换行）。

获取方式：浏览器登录 `https://mail.ypan.hk` 后，F12 → Network → 任选一个 `novel` 请求 → 复制 `Cookie` 请求头内容，粘贴进 `cookie.txt`。

```
# scripts/cookie.txt 示例（内容为一行 Cookie）
__Secure-next-auth.session-token=xxx; your_cookie_key=xxx
```



### 3. 运行

```bash
cd scripts

# 爬取全部三本书
python3 crawl_all.py

# 只爬某一本
python3 crawl_all.py 李氏庄园
python3 crawl_all.py 回信券风暴

# 查看可用书名
python3 crawl_all.py --list
```

输出自动写入 `~/Downloads/小说/{书名}/`，已存在的图片会跳过，不会重复下载。

---

## 输出说明

- **单章文件** `NN_chapter.txt`：Markdown 文本，含章节标题。
- **全集文件** `{书名}_全集.txt`：全章节按顺序合并。
- **插图**：正文中图片以原 Markdown 标记保留，路径改写为本地相对地址，如 `![李明修吸烟](assets/image.png)`，用支持 Markdown 的阅读器（Typora / VS Code / Obsidian 等）打开时可直接显示对应图片。

---

## 脚本参数

| 用法 | 说明 |
|---|---|
| `python3 crawl_all.py` | 爬取所有书 |
| `python3 crawl_all.py <书名>` | 只爬指定书 |
| `python3 crawl_all.py --list` | 打印可用书名 |

新增一本小说时，编辑 `crawl_all.py` 顶部 `BOOKS` 列表，追加元组即可：

```python
BOOKS = [
    ("书名", "book-xxxx", "封面文件名.png", [
        ("01", "chapter-xxxx"), ("02", "chapter-yyyy"), …
    ]),
]
```

---

## 推送到 GitHub

```bash
cd ~/Downloads/小说
git init
git add .
git commit -m "chore: init novel archive"
git branch -M main
git remote add origin git@github.com:WhyPilotXia/mail_novels.git
git push -u origin main
```

> 先确认 `.gitignore` 已生效，避免 `cookie.txt` 被推送到远端。可用 `git status` 检查暂存文件清单。

---

