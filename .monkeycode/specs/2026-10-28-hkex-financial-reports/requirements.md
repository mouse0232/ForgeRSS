# Requirements Document

## Introduction

ForgeRSS 已支持巨潮资讯网（A 股）公司公告 RSS。本需求新增港交所披露易（HKEXnews）港股财报 RSS：从披露易最新上市公司信息 JSON 拉取公告，筛选财务报告类文件，生成与巨潮公告生成器同构的 RSS Feed，并可选下载附件。

数据源为披露易公开 JSON：`https://www1.hkexnews.hk/ncms/json/eds/lcisehk7relsdc_1.json`（分页文件名为 `lcisehk7relsdc_{n}.json`）。该接口返回主板/GEM 最新呈交文件，其中包含年报、中期报告、末期/中期/季度业绩等财报类条目，也包含停牌、通函、翌日披露报表等非财报条目。系统默认只输出财报类条目。

## Glossary

- **System**: ForgeRSS 及其财经 RSS 生成器子系统。
- **HKEXnews JSON**: 港交所披露易最新上市公司信息接口，路径模式为 `/ncms/json/eds/lcisehk7relsdc_{n}.json`。
- **财报条目**: 满足预设一级/二级标题类别（t1Code / t2Code）或用户配置过滤条件的财务报告类呈交文件，包括年报、中期报告、末期业绩、中期业绩、季度业绩。
- **Article**: `generators.base.Article`，RSS 条目的标准数据模型。
- **Feed**: 系统生成的 RSS 2.0 文件，默认路径为 `feeds/feed_hkex_financial_reports.xml`。
- **附件**: 财报条目对应的 PDF 或 HTM 原文文件。

## Requirements

### Requirement 1: 港股财报数据获取

**User Story:** AS 财经信息订阅者, I want 系统定期从披露易 JSON 拉取港股最新财报呈交, so that 我可以用 RSS 阅读器跟踪港股财务披露。

#### Acceptance Criteria

1. WHEN 生成器启动, the System SHALL 从 `https://www1.hkexnews.hk/ncms/json/eds/lcisehk7relsdc_{n}.json` 按页拉取 `newsInfoLst`。
2. WHEN HKEXnews JSON 返回 HTTP 200 且包含 `newsInfoLst`, the System SHALL 解析每条记录的 `newsId`、`title`、`lTxt`、`webPath`、`ext`、`size`、`stock`、`relTime`、`t1Code`、`t2Code`、`market`。
3. WHEN 当前页条目数达到该页容量（实测约 500 条）且尚未满足条数上限, the System SHALL 继续请求下一页，直到 `n` 超过 `maxNumOfFile`、当前页条目数为 0、或已收集到配置的最大条数。
4. IF HKEXnews JSON 请求失败或返回非 JSON, the System SHALL 记录错误并保留已有 Feed 文件。

### Requirement 2: 财报筛选

**User Story:** AS 财经信息订阅者, I want 默认只看到年报、中期报告和业绩公告, so that Feed 不被停牌、通函、翌日披露报表淹没。

#### Acceptance Criteria

1. WHEN 未配置自定义过滤条件, the System SHALL 仅保留满足下列任一条件的条目：`t1Code` 为 `40000` 且 `t2Code` 包含 `40100`（年报）或 `40200`（中期报告）；或 `t1Code` 为 `10000` 且 `t2Code` 包含 `13300`（末期业绩）、`13400`（中期业绩）或 `13600`（季度业绩）。
2. WHEN 环境变量 `HKEX_T2_CODES` 已设置, the System SHALL 改为按该逗号分隔的二级标题代码列表过滤。
3. WHEN 环境变量 `HKEX_KEYWORDS` 已设置, the System SHALL 仅保留标题 `title` 或类别文本 `lTxt` 包含任一关键词的条目。
4. WHEN 环境变量 `HKEX_STOCKS` 已设置, the System SHALL 仅保留 `stock[].sc` 命中该逗号分隔股票代码列表的条目（代码按去前导零后比较，例如 `00700` 与 `700` 视为同一代码）。
5. WHEN 同一 `newsId` 或同一附件 URL 在本次拉取中重复出现, the System SHALL 只保留一条。

### Requirement 3: RSS 条目映射

**User Story:** AS RSS 阅读器用户, I want 每条港股财报包含公司名、代码、类别、发布时间与原文链接, so that 我能直接打开披露易附件。

#### Acceptance Criteria

1. WHEN 一条财报条目解析成功, the System SHALL 生成 `Article`，`title` 格式为 `[股票简称] 原标题`；若一条记录对应多只股票，股票简称用顿号连接。
2. WHEN `webPath` 非空, the System SHALL 将 `Article.url` 设为 `https://www1.hkexnews.hk` 与 `webPath` 的拼接结果。
3. WHEN `relTime` 为 `DD/MM/YYYY HH:MM` 格式, the System SHALL 按 `Asia/Hong_Kong` 时区解析为带时区的发布时间，再转换为 UTC 写入 `published_at`。
4. WHEN 生成条目正文, the System SHALL 包含股票代码、股票简称、披露类别（`lTxt`）、发布时间、文件类型、文件大小、原文链接。
5. WHEN 条目写入 Feed, the System SHALL 将 `category` 设为 `港股财报`，将 `author` 设为 `HKEXnews`。

### Requirement 4: 附件下载与运行配置

**User Story:** AS 本地部署用户, I want 可选把港股财报 PDF 归档到本地, so that 我能离线阅读，行为与巨潮公告生成器一致。

#### Acceptance Criteria

1. WHEN `HKEX_DOWNLOAD_PDF` 为 `true` 且附件扩展名为 `pdf`, the System SHALL 将文件保存到 `downloads/hkex_pdfs/<公司名>_<股票代码>/`，文件名由股票代码与清洗后的标题组成。
2. WHEN 目标 PDF 文件已存在, the System SHALL 跳过下载并在条目正文中给出已有本地路径。
3. WHEN 生成器运行, the System SHALL 读取以下环境变量（括号内为默认值）：`HKEX_MAX_ITEMS`（50）、`HKEX_MAX_PAGES`（1）、`HKEX_REQUEST_INTERVAL`（1.0 秒）、`HKEX_DOWNLOAD_PDF`（false）、`HKEX_FEED_NAME`（`hkex_financial_reports`）、`HKEX_FEED_TITLE`、`HKEX_FEED_DESCRIPTION`、`HKEX_DAYS`（7）。
4. WHEN `HKEX_DAYS` 已设置, the System SHALL 丢弃发布时间早于「当前香港日期减去 N 天」的条目。

### Requirement 5: 集成与调度

**User Story:** AS 项目维护者, I want 港股财报生成器注册进现有运行入口并支持定时更新, so that 使用方式与巨潮公告源一致。

#### Acceptance Criteria

1. WHEN 用户执行 `python scripts/run_single.py hkex_financial_reports`, the System SHALL 运行港股财报生成器并写出 `feeds/feed_{FEED_NAME}.xml`。
2. WHEN 生成器完成一次成功运行, the System SHALL 通过 `BaseFeedGenerator` 的 URL 去重、JSON cache 与 SQLite 存储合并历史条目。
3. WHEN 项目在 GitHub Actions 中启用港股财报工作流, the System SHALL 每 6 小时运行一次，默认不下载 PDF，并将更新后的 Feed 提交到仓库。
4. WHEN 用户以模块方式运行 `python -m generators.finance.hkex_financial_reports`, the System SHALL 接受与环境变量对应的命令行参数（`--stocks`、`--keywords`、`--t2-codes`、`--days`、`--max`、`--download-pdf`、`--full`）。
