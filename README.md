# 邮件小说批量爬取

自动将「Mail Web」小说平台（`mail.ypan.hk`）上的小说按本抓取为 Markdown 文本，同时下载封面与正文插图，归入当前仓库的 `{书名}/` 目录，方便离线阅读与归档。

本项目为自用工具，所有内容用于个人阅读备份。

---

## 目录结构

```
小说/
├── README.md              # 本说明
├── .gitignore             # Git 忽略规则（含 cookie 与输出目录）
├── scripts/               # 爬取脚本与配置
│   ├── crawl_all.py       # 本地动态书目同步：正文 + 封面 + 插图 + 单章/全集
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
├── 股神牛久盛/
└── 名将之后/
```

---

## quick start

### 1. 安装 / 依赖

需要 Python 3.9+；同步书架配置和构建另需 Node.js 22+。均使用标准库，无需安装第三方依赖。

```bash
python3 --version
node --version
```

### 2. 配置 Cookie

平台需要登录态。将浏览器中的 Cookie 复制到 `scripts/cookie.txt`（**一行**，无换行）。

获取方式：浏览器登录 `https://mail.ypan.hk` 后，F12 → Network → 任选一个 `novel` 请求 → 复制 `Cookie` 请求头内容，粘贴进 `cookie.txt`。

```
# scripts/cookie.txt 示例（内容为一行 Cookie）
__Secure-next-auth.session-token=xxx; your_cookie_key=xxx
```



### 3. 本地获取，再提交推送

以下命令在仓库根目录运行。爬虫只在本机访问 `/novel/text` 获取完整书目及章节 ID，再下载所选书的正文和图片；不再硬编码书目、封面或章节列表。

```bash
python3 scripts/crawl_all.py --list
python3 scripts/crawl_all.py 名将之后
python3 scripts/crawl_all.py
```

`--list` 只显示最新书目与章数，不改文件；指定书名时只同步该书；不指定则同步所有书。每本书下载成功后自动更新 `js/books.js`，保留旧书的 key、目录和访问链接，新书使用稳定远端 ID 作为 key。

章节与图片写入当前仓库目录，不受运行时工作目录影响。新书缺少封面时自动生成 `assets/_cover.svg` 占位封面；纯图片正文同样会下载到本地。已有图片默认复用，原站同名图片更新时可加 `--refresh-images`。正文每次重新下载，更新标题与内容。

先下载到临时目录，一本书的全部正文和图片成功后才替换该书文件。请求、鉴权或图片失败会非零退出，不用残缺数据覆盖该书旧文件。远端移除的章节会归档到 Git 忽略的 `.crawl-backups/`，避免下次构建继续收录；不自动删除整本本地小说。章节按接口列表顺序编号，远端插入或重排章节时，旧的按编号阅读记录可能需要重新选择。

Cookie 从本地 `scripts/cookie.txt` 读取，也可通过环境变量 `MAIL_NOVEL_COOKIE` 或 `--cookie-file` 指定；仅发往 `https://mail.ypan.hk`，不打印、不写入公开文件、不转发到外站或重定向地址。Cookie 过期时在本机更新后重试。

本地同步后检查、测试、构建，再提交推送：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend.test.cjs
python3 scripts/build_site.py
git status --short
git diff
git add .
git diff --cached --name-only
git commit -m "update novels from local crawl"
git push origin main
```

GitHub Actions 只使用推送后的仓库文件构建静态站点，不运行爬虫、不访问原站、不使用 Cookie。网页也只读取 Pages 中的静态目录、正文和图片。

---

## 输出说明

- **单章文件** `NN_chapter.txt`：Markdown 文本，含章节标题。
- **全集文件** `{书名}_全集.txt`：全章节按顺序合并。
- **插图**：正文中图片以原 Markdown 标记保留，路径改写为本地相对地址，如 `![李明修吸烟](assets/image.png)`，用支持 Markdown 的阅读器（Typora / VS Code / Obsidian 等）打开时可直接显示对应图片。

---

## 脚本参数

| 用法 | 说明 |
|---|---|
| `python3 scripts/crawl_all.py` | 本地获取当前全部书目并同步所有书 |
| `python3 scripts/crawl_all.py <书名或ID> ...` | 只同步指定书，可指定多本 |
| `python3 scripts/crawl_all.py --list` | 只查询最新书目，不写小说文件 |
| `python3 scripts/crawl_all.py --refresh-images` | 同步所有书，强制重新下载图片和封面 |
| `python3 scripts/crawl_all.py --cookie-file <路径>` | 使用指定的本地 Cookie 文件 |

新增小说无需修改爬虫或手工登记书架；本地运行同步命令后提交新增目录和更新后的 `js/books.js` 即可。

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
| 阅读《名将之后》 | [打开阅读](https://whypilotxia.github.io/mail_novels/reader.html?book=book-mtvc2rkc-0gmmdr) |

支持功能：书架封面展示、正文阅读、正文内嵌插图、上一章 / 下一章切换。

### 自动构建 / 更新 Pages

Pages 的 Source 使用 **GitHub Actions**。每次推送到 `main`，工作流 `.github/workflows/pages.yml` 会先运行测试，再执行 `python3 scripts/build_site.py`，最后部署 `_site/`。

- 每次构建扫描 `js/books.js` 配置的小说文件夹，以实际 `NN_chapter.txt` 文件为准，从首行 `# 标题` 提取目录标题，按编号数值排序，支持编号缺口和 100 章以上。
- 新增、删除章节，修改标题或正文，都会在下一次成功构建后生效。不依赖仓库中旧的 `chapters.json`，构建会在发布目录内重新生成它。
- 书架每本书只请求一个 `chapters.json` 统计章节数，不请求任何章节正文；阅读器只请求目录和当前章正文，切章按需加载，已读章节内存缓存。目录加载失败会提示重试，不再逐章探测。
- 上下章按钮显示相邻章节标题；第一章隐藏上一章，最后一章隐藏下一章，不显示灰色按钮；仅一章时隐藏整个翻章栏。保存的阅读记录优先使用章节编号，删除前面章节不会把记录错移到其他章。
- 发布资源附带构建内容版本号；目录和正文请求重新校验缓存，避免旧脚本、旧目录和旧正文混用。已打开的页面需要刷新才能使用新版本。
- 本地运行爬虫时会自动登记新书并更新简介、封面和目录；提交 `js/books.js` 与小说目录后再构建。手工新增非原站小说时仍需自行登记配置；目录手工改名也需同步 `dir`。
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

