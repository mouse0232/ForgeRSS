# 财经数据 RSS 生成器

## 巨潮资讯网公告订阅

### 三种订阅方式

#### 1) 按主题关键词（推荐）

适合订阅「事件类公告」：股权激励、业绩快报、回购等。

```bash
# 单个主题
CNINFO_KEYWORDS="股权激励" python scripts/run_single.py cninfo_announcements

# 多主题
CNINFO_KEYWORDS="股权激励,业绩快报,回购" python scripts/run_single.py cninfo_announcements
```

#### 2) 按分类

适合订阅「特定类型公告」：年报、半年报、季报等。

```bash
# 全市场年报
CNINFO_CATEGORY=category_ndbg_szsh python scripts/run_single.py cninfo_announcements

# 业绩预告
CNINFO_CATEGORY=category_yjygjxz_szsh python scripts/run_single.py cninfo_announcements

# 多个分类用英文分号隔开（逗号会被巨潮忽略，返回全部公告）
CNINFO_CATEGORY="category_ndbg_szsh;category_sjdbg_szsh" python scripts/run_single.py cninfo_announcements
```

常用分类代码（巨潮没有公开清单；其他分类可在巨潮公告查询页选好分类后，从浏览器网络请求 `hisAnnouncement/query` 的 `category` 参数里取）：

| 代码 | 含义 |
|---|---|
| `category_ndbg_szsh` | 年度报告 |
| `category_bndbg_szsh` | 半年度报告 |
| `category_yjdbg_szsh` | 一季度报告 |
| `category_sjdbg_szsh` | 三季度报告 |
| `category_sf_szsh` | 首发（上新企业） |
| `category_yjygjxz_szsh` | 业绩预告 |
| `category_gqjl_szsh` | 股权激励 |
| `category_zj_szsh` | 增减持 |
| `category_dshgg_szsh` | 董事会公告 |
| `category_gddh_szsh` | 股东大会 |

巨潮没有单独的业绩快报分类，可改用关键词：`CNINFO_KEYWORDS="业绩快报"`。同时配置了 `CNINFO_KEYWORDS` 时，`CNINFO_CATEGORY` 不生效。

#### 3) 按市场（默认）

不配置任何关键词/分类时，按市场拉最新公告。

```bash
# 沪深两市最新（默认）
python scripts/run_single.py cninfo_announcements

# 只看深市
CNINFO_MARKETS=szse python scripts/run_single.py cninfo_announcements
```

### 命令行参数

```bash
python -m generators.finance.cninfo_announcements \
  --keywords "股权激励" \         # 主题关键词
  --category "" \                  # 分类（可选）
  --markets "szse,sse" \           # 市场
  --days 7 \                       # 最近 N 天
  --max 30 \                       # 最多获取多少条
  --download-pdf                   # 同时下载 PDF
```

CI 用两个独立 Action，分别覆盖输出文件名：

- 年报/半年报：`CNINFO_CATEGORY=category_ndbg_szsh;category_bndbg_szsh` → `feeds/feed_cninfo_annual_reports.xml`
- 上新企业：`CNINFO_CATEGORY=category_sf_szsh`，标题须含「招股说明书」 → `feeds/feed_cninfo_ipo.xml`

本地不设 `CNINFO_FEED_NAME` 时，仍输出 `feeds/feed_cninfo_announcements.xml`。

### 输出位置

- **RSS Feed**：`feeds/feed_cninfo_announcements.xml`（可用 `CNINFO_FEED_NAME` 改文件名）
- **PDF 文件**：`downloads/cninfo_pdfs/<公司名>_<股票代码>/<标题>.pdf`

### 频率建议

- 个人使用：6 小时更新一次
- 请求间隔：默认 2 秒（`CNINFO_REQUEST_INTERVAL`）
- 默认获取最近 7 天

### 风险提示

⚠️ 仅供个人学习使用，不得用于商业目的。建议控制请求频率，避免被封 IP。

## 披露易港股财报订阅

从港交所披露易最新上市公司信息 JSON 拉取呈交，默认只保留年报、中期/半年度报告，以及招股/上市文件（发售以供认购、介绍上市、发售现有证券）。

```bash
python scripts/run_single.py hkex_financial_reports

python -m generators.finance.hkex_financial_reports \
  --stocks "700,941" \
  --days 7 \
  --max 30
```

| 环境变量 | 默认 | 含义 |
|---|---|---|
| `HKEX_T2_CODES` | `40100,40200,30500,30600,30700` | 二级标题代码白名单 |
| `HKEX_KEYWORDS` | 空 | 标题或类别文本关键词 |
| `HKEX_STOCKS` | 空 | 股份代号，去前导零比较 |
| `HKEX_DAYS` | 7 | 相对发放日的天数窗 |
| `HKEX_MAX_ITEMS` | 50 | Feed 条数上限 |
| `HKEX_MAX_PAGES` | 1 | 最多拉取的 JSON 页数 |
| `HKEX_DOWNLOAD_PDF` | false | 是否下载 PDF |
| `HKEX_REQUEST_INTERVAL` | 1.0 | 翻页间隔秒 |

输出：

- RSS Feed：`feeds/feed_hkex_financial_reports.xml`
- PDF（可选）：`downloads/hkex_pdfs/<公司名>_<股票代码>/<标题>.pdf`

标题类别数字码见 `.monkeycode/specs/2026-10-28-hkex-financial-reports/hkexnews-search-filter.md`。
