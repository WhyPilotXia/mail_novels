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

## 在线阅读（GitHub Pages）

本仓库已启用 GitHub Pages，可通过网页直接浏览小说书架、封面与章节内容。

- **仓库**：https://github.com/WhyPilotXia/mail_novels
- **在线书架**：https://whypilotxia.github.io/mail_novels/

### 阅读入口

| 页面 | 地址 |
|---|---|
| 书架（选书） | `https://whypilotxia.github.io/mail_novels/` |
| 阅读《李氏庄园》 | `.../mail_novels/reader.html?book=lishizhuangyuan` |
| 阅读《回信券风暴》 | `.../mail_novels/reader.html?book=huixinquanfengbao` |
| 阅读《股神牛久盛》 | `.../mail_novels/reader.html?book=gushenniujiusheng` |

支持功能：书架封面展示、正文阅读、正文内嵌插图、上一章 / 下一章切换。

### 自动构建 / 更新 Pages

Pages 的 Source 使用 **GitHub Actions**。每次推送到 `main`，工作流 `.github/workflows/pages.yml` 会先运行测试，再执行 `python3 scripts/build_site.py`，最后部署 `_site/`。

- 每次构建扫描 `js/books.js` 配置的小说文件夹，以实际 `NN_chapter.txt` 文件为准，从首行 `# 标题` 提取目录标题，按编号数值排序，支持编号缺口和 100 章以上。
- 新增、删除章节，修改标题或正文，都会在下一次成功构建后生效。不依赖仓库中旧的 `chapters.json`，构建会在发布目录内重新生成它。
- 书架每本书只请求一个 `chapters.json` 统计章节数，不请求任何章节正文；阅读器只请求目录和当前章正文，切章按需加载，已读章节内存缓存。目录加载失败会提示重试，不再逐章探测。
- 上下章按钮显示相邻章节标题；第一章隐藏上一章，最后一章隐藏下一章，不显示灰色按钮；仅一章时隐藏整个翻章栏。保存的阅读记录优先使用章节编号，删除前面章节不会把记录错移到其他章。
- 发布资源附带构建内容版本号；目录和正文请求重新校验缓存，避免旧脚本、旧目录和旧正文混用。已打开的页面需要刷新才能使用新版本。
- 新增一本书时，在 `js/books.js` 添加书名、目录、封面、简介和唯一 key，并提交小说目录；新增到现有书的章节无需改 JavaScript。目录改名也需要同步修改 `dir`。
- 构建不登录原网站、不自动爬取，不需要 Cookie。它只发布 HTML、JS、CSS、章节正文、生成的目录及图片，不会发布 `scripts/`、Cookie、全集或其他未列入发布范围的文件。

提交小说文件变化后推送即可；本机未提交或未推送的改动不会影响线上：

```bash
git add .
git commit -m "update novels"
git push origin main
```

可以在 [Actions](https://github.com/WhyPilotXia/mail_novels/actions) 查看构建部署状态，或手动运行工作流重新构建。构建失败会保留上一次成功发布的站点。

### 本地构建与验证

构建需要 Python 3.9+ 和 Node.js 22+，均只用标准库，无需安装第三方依赖；爬虫原有使用方式不变。在项目根目录执行：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend.test.cjs
python3 scripts/build_site.py
python3 -m http.server 54562 --directory _site
```

构建会重新生成 `_site/`（仅构建产物，勿在里面手工编辑），不改小说源文件或本地旧目录清单。浏览器打开 [本地书架](http://localhost:54562/) 验证。

> Pages 当前公开可访问。请仅发布有权公开的内容；不要提交 Cookie 或其他敏感文件，即使私有仓库的 Pages 也不应默认视为私密。

