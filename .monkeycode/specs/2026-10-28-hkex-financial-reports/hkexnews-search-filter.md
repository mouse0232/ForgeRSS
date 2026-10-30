# 披露易（HKEXnews）搜索与标题类别参考

Feature: hkex-financial-reports
Updated: 2026-10-28
Audience: 后续要接披露易数据的开发者

港交所官网「标题类别」页只给中英文名称，不给数字码。数字码、下拉框选项、搜索提交字段，全部来自披露易前端加载的官方 JSON 和 JS。本文把码表、URL 拼法、搜索参数和财报默认集一次写清，避免再从 `lTxt` 反推。

核对日期：2026-10-28。码表 `count` 会随时间变，代码和名称以当时拉取的 JSON 为准。

---

## 1. 两套入口，不要混用

| 用途 | 入口 | 是否适合 RSS 轮询 |
|---|---|---|
| 最新呈交快照 | GET `/ncms/json/eds/{filename}_{n}.json` | 适合。无会话、无验证码、分页明确 |
| 按股票 / 标题 / 日期历史检索 | 标题搜索页 `titlesearch.xhtml` + `titleSearchServlet.do` | 不适合做默认定时源。有 JSF ViewState，结果上限 1000 条 |

港股财报 RSS 用第一套。第二套只在需要「某一只股票过去 12 个月年报」时再用。

页面：

- 最新上市公司信息：`https://www1.hkexnews.hk/listedco/listconews/index/lci.html`
- 标题搜索：`https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=ZH`
- 英文搜索：`https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=EN`

Host 一律走 `www1.hkexnews.hk`。`www.hkexnews.hk` / `sc.hkexnews.hk` 的搜索页会把表单 action 指回 `www1`。

---

## 2. 官方码表（权威来源）

搜索页配置文件声明码表路径：

- 繁中：`https://www1.hkexnews.hk/ncms/eds/titlesearch/config_c.js`
- 英文：`https://www1.hkexnews.hk/ncms/eds/titlesearch/config.js`（没有 `config_e.js`）

`titlesearch.js` 的 `initHeadlineCategory()` 并行加载三级码表，填「标题类别」下拉框；`initDocumentType()` 加载文件类别，只在「2007-06-24 及之前」模式使用。

### 2.1 文件一览

语言后缀：`_c` = 繁中，`_e` = 英文。同一 `code` 两边一一对应。

| 文件 | URL | 条数（2026-10-28） | 用途 |
|---|---|---|---|
| 一级标题 | `/ncms/script/eds/tierone_{c\|e}.json` | 20 | 搜索下拉第一层；最新 JSON 的 `t1Code` |
| 二级分组 | `/ncms/script/eds/tiertwogrp_{c\|e}.json` | 22 | 搜索下拉第二层（仅部分一级有分组） |
| 二级标题 | `/ncms/script/eds/tiertwo_{c\|e}.json` | 294 | 搜索下拉最底层；最新 JSON 的 `t2Code` |
| 文件类别 | `/ncms/script/eds/doc_{c\|e}.json` | 17 | 仅 1999-04-01 ～ 2007-06-24 |
| 在市股票 | `/ncms/script/eds/activestock_sehk_{c\|e}.json` | 主板约 17270 | 代码 → 内部 `stockId` |
| 在市创业板 | `/ncms/script/eds/activestock_gem_c.json` | 约 305 | GEM 股票 |
| 已除牌 | `/ncms/script/eds/inactivestock_sehk_{c\|e}.json` | 约 884 | 历史检索 |

`titlesearch.js` 加载时带 cache bust，直连上述 URL 即可，不需要 cookie。

### 2.2 记录结构

`tierone_*.json`：

```json
{"code": "10000", "name": "公告及通告", "count": 4790}
```

`tiertwogrp_*.json`：

```json
{"code": "3", "name": "財務資料", "t1code": "10000"}
```

`tiertwo_*.json`：

```json
{"code": "13300", "name": "末期業績", "t1code": "10000", "t2Gcode": "3", "count": 121}
```

`t2Gcode = "-1"` 表示该一级下面没有分组，二级直接挂在一级下（年报 `40100`、翌日披露 `50100` 都是这种）。

`doc_*.json`：

```json
{"code": "11000", "name": "業績公告"}
```

注意：文件类别码 `11000`（业绩公告）和一级标题码 `10000`（公告及通告）不是同一套。2007-06-25 之后不要用 `doc_*.json` 去过滤最新 JSON。

### 2.3 一级标题完整表

`count` 是搜索页当时的命中估计，只作量级参考。

| t1Code | 繁中 | English |
|---|---|---|
| 10000 | 公告及通告 | Announcements and Notices |
| 20000 | 通函 | Circulars |
| 30000 | 上市文件 | Listing Documents |
| 40000 | 財務報表/環境、社會及管治資料 | Financial Statements/ESG Information |
| 50000 | 翌日披露報表 | Next Day Disclosure Returns |
| 51000 | 股份購回報告 (2009年1月1日前) | Share Buyback Reports (Before 1 January 2009) |
| 51500 | 月報表 | Monthly Returns |
| 52000 | 委任代表表格 | Proxy Forms |
| 53000 | 公司資料報表 | Company Information Sheet |
| 54000 | 憲章文件 | Constitutional Documents |
| 55000 | 合併守則 - 交易披露 | Takeovers Code - dealing disclosures |
| 56000 | 展示文件 | Documents on Display |
| 57000 | 展示文件（債務證券發行計劃） | Documents on Display (Debt Issuance Programmes) |
| 58000 | 展示文件（債務證券） | Documents on Display (Debt Securities) |
| 59000 | 展示文件（結構性產品） | Documents on Display (Structured Products) |
| 70000 | 債券及結構性產品 | Debt and Structured Products |
| 80000 | 交易所買賣基金的交易資料 | Trading Information of Exchange Traded Funds |
| 81000 | 槓桿及反向產品的交易資料 | Trading Information of Leveraged and Inverse Products |
| 90000 | 監管者發出的公告及消息 | Regulatory Announcement & News |
| 91000 | 申請版本、整體協調人公告及聆訊後資料集 | Application Proofs, OC Announcements and Post Hearing Information Packs or PHIPs |

没有二级码的一级（过滤时只看 `t1Code`）：`51000`、`51500`、`52000`、`53000`、`54000`、`55000`、`56000`、`57000`、`58000`、`59000`、`80000`、`81000`、`90000`。

### 2.4 公告及通告（10000）下的二级分组

| t2Gcode | 繁中 | English |
|---|---|---|
| 1 | 關連交易 | Connected Transactions |
| 2 | 公司狀況變動及委員會/公司變動 | Corporate Positions and Committees/Corporate Changes |
| 3 | 財務資料 | Financial Information |
| 4 | 會議/表決 | Meetings/Voting |
| 5 | 新上市（上市發行人/新申請人） | New Listings (Listed Issuers/New Applicants) |
| 6 | 須予公布的交易 | Notifiable Transactions |
| 7 | 重組/股權變動/主要改動/公眾持股量/上市地位 | Reorganisation / Shareholding / Listing Status |
| 8 | 證券/股本 | Securities/Share Capital |
| 9 | 雜項 | Miscellaneous |

通函（20000）有一套平行分组（t2G 10–16），名称接近，代码不同。债券及结构性产品（70000）另有牛熊证 / 衍生权证等分组。

### 2.5 下拉框如何写成三个码

`titlesearch.js` `_onHeadlineCategory`：

1. 只选一级 → `t1code=<一级>`, `t2code=-2`, `t2Gcode=-2`
2. 选到分组 → `t1code=<一级>`, `t2code=<分组>`, `t2Gcode=-2`（中间层先写入 t2code）
3. 选到具体二级 → `t1code=<一级>`, `t2Gcode=<分组>`, `t2code=<二级>`

未选时三个字段都是 `-2`。重置时写成空字符串。

匹配最新 JSON 时不要用 `-2`。一条呈交的 `t2Code` 可能是逗号拼接的多个二级码，求交非空即命中。

---

## 3. 最新上市公司信息 JSON（RSS 推荐）

前端：`https://www1.hkexnews.hk/ncms/js/lci.js`，函数 `getTableJsonFile`。

### 3.1 文件名拼法

```text
/ncms/json/eds/
  + {tab}          lci | spd | oth
  + {board}        sehk | gem
  + {range}        1=当日最新 | 7=近 7 天
  + {sort}         rels | code | name
  + {dir}          d=降序 | a=升序
  + {lang}         c=繁中 | e=英文
  + _{page}.json
```

| 场景 | 文件名 | 2026-10-28 实测 |
|---|---|---|
| 主板近 7 天、按发放时间降序、繁中 | `lcisehk7relsdc_{n}.json` | 500 条/页，`maxNumOfFile=5` |
| 同上、英文 | `lcisehk7relsde_{n}.json` | 500 条/页，`maxNumOfFile=5` |
| 主板当日最新、繁中 | `lcisehk1relsdc_1.json` | 约 419 条，`maxNumOfFile=1` |
| 创业板近 7 天、繁中 | `lcigem7relsdc_1.json` | 约 130 条，`maxNumOfFile=1` |
| 结构性产品近 7 天 | `spdsehk7relsdc_1.json` | 约 483 条 |
| 其他（ETF 等）近 7 天 | `othsehk7relsdc_1.json` | 500 条/页，`maxNumOfFile=3` |
| 按股份代号排序 | `lcisehk7codedc_{n}.json` | 与 rels 同快照，顺序不同 |

完整 URL 例：

```text
https://www1.hkexnews.hk/ncms/json/eds/lcisehk7relsdc_1.json
```

页码 `n` 从 1 起，上界是该文件自己的 `maxNumOfFile`。第 1 页不够再拉 2、3…，不要预先假设总是 5 页。

时间戳索引（前端用来判断要不要整表刷新）：

```text
https://www1.hkexnews.hk/ncms/json/eds/genindex_sehk.json
https://www1.hkexnews.hk/ncms/json/eds/genindex_gem.json
```

`lci.html` 默认 Tab 是主板上市公司 + 近 7 天 + 发放时间降序 + 跟页面语言。港股财报 RSS 对齐这个默认：`lcisehk7relsdc_{n}.json`。

### 3.2 顶层字段

```json
{
  "genDate": 1793169772258,
  "maxNumOfFile": 5,
  "newsInfoLst": [ ]
}
```

| 字段 | 含义 |
|---|---|
| `genDate` | 快照生成时间，毫秒时间戳 |
| `maxNumOfFile` | 当前快照最大页号 |
| `newsInfoLst` | 本页条目，最多约 500 条 |

### 3.3 条目字段

```json
{
  "newsId": 12385456,
  "title": "海外監管公告",
  "lTxt": "公告及通告 - [海外監管公告-企業管治相關事宜]",
  "sTxt": "公告及通告 - [海外監管公告-企業管治相關事宜]",
  "ext": "pdf",
  "size": "158KB",
  "webPath": "/listedco/listconews/sehk/2026/1028/2026102800209_c.pdf",
  "market": "SEHK",
  "multi": 0,
  "stock": [{"sc": "00371", "sn": "北控水務集團"}],
  "relTime": "28/10/2026 12:13",
  "t1Code": "10000",
  "t2Code": "19830",
  "dod": "N",
  "dodPath": "NaN"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `newsId` | int | 呈交唯一 ID，适合做 RSS guid |
| `title` | str | 文件标题 |
| `lTxt` / `sTxt` | str | 「一级名称 - [二级名称]」，展示用；过滤请用代码 |
| `ext` | str | `pdf` 或 `htm` |
| `size` | str | 如 `334KB` |
| `webPath` | str | 站点相对路径，缺省时不要拼附件 URL |
| `market` | str | 主板快照里是 `SEHK` |
| `multi` | 0/1 | 是否多文件呈交 |
| `stock` | list | `sc` 五位代号（含前导零），`sn` 简称；H 股/回购股份等可多只 |
| `relTime` | str | `DD/MM/YYYY HH:MM`，时区 `Asia/Hong_Kong` |
| `t1Code` | str | 一级码，单值 |
| `t2Code` | str | 二级码；多个时逗号拼接，如 `18160,18500,18540,19250` |
| `dod` / `dodPath` | str | 收购守则展示文件；常见 `dod=N` |

附件绝对地址：

```text
https://www1.hkexnews.hk{webPath}
```

请求头建议：

```text
User-Agent: Mozilla/5.0 ...
Referer: https://www1.hkexnews.hk/listedco/listconews/index/lci.html
Accept: application/json
```

### 3.4 语言差异

`lcisehk7relsdc`（繁中）和 `lcisehk7relsde`（英文）是同一快照、同一 `newsId`。英文文件的 `title` / `lTxt` 换成英文；部分发行人只在中文区放了文件，英文 `title` 会变成占位句：

> An announcement has just been published by the issuer in the Chinese section of this website, a corresponding version of which may or may not be published in this section

港股财报 RSS 默认繁中源。

---

## 4. 标题搜索页（历史检索）

前端：

- 配置：`/ncms/eds/titlesearch/config_c.js` 或 `config.js`
- 表单逻辑：`/ncms/js/titlesearch.js`
- 结果表：`/ncms/js/titlesearch_research.js`
- 搜索面板 HTML：页面里 `data-include-html="titleSearchSearchPanel_c.html"`

### 4.1 三种搜索模式

| 表单 searchType | 内部整型 | 日期窗 | 过滤维度 |
|---|---|---|---|
| `rbAfter2006` | 1 | 2007-06-25 起 | 标题类别 `t1code` / `t2Gcode` / `t2code` |
| `rbPrior2006` | 2 | 1999-04-01 ～ 2007-06-24 | 文件类别 `documentType`（`doc_*.json`） |
| `rbAll` | 0 | 1999-04-01 起 | 两者都不用；未选股票时跨度最多 1 个月 |

`titlesearch.js` 把 `rbAfter2006` 写成 `this.form.searchType.value = 1`（整型），结果刷新走 hidden 字段 `searchTypeInt`。

未选股票时：全市场 + 无类别，跨度最多 `SearchDocAllMaxMonthRange = 1` 个月。选了股票后，单票跨度最多 `SearchDocSingleMaxMonthRange = 12` 个月。结果最多 1000 条（`ViewMoreRecords`）。

### 4.2 首次提交（整页 POST）

`_onSearch` → `preprocessMainForm()` → `document.TitleSearchPanel.submit()`。

Action：

```text
https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh
```

英文 `lang=en`。日期会从 `YYYY/MM/DD` 收成 `YYYYMMDD` 写入 `from` / `to`。

JS 写入的字段：`stockId`、`market`、`category`、`searchType`、`documentType`、`t1code`、`t2code`、`t2Gcode`、`from`、`to`。

`market` 恒为 `SEHK`（配置项 `titleSearchConfig.market`）。

页面 HTML 里还能看到 JSF 隐藏域（`javax.faces.ViewState`、`tierOneId`、`tierTwoId`、`tierTwoGpId` 等）。整页提交依赖这些域，不适合无头脚本直接仿。历史检索请走下面的 servlet。

### 4.3 结果刷新（GET servlet）

`titlesearch_research.js` 的 `searchAgain()`：

```text
GET https://www1.hkexnews.hk/search/titleSearchServlet.do
```

Query：

| 参数 | 来源 | 例 |
|---|---|---|
| `lang` | `C` 或 `E`（hidden `#lang`） | `C` |
| `market` | 配置 | `SEHK` |
| `stockId` | 内部 ID，不是股份代号 | `7609`（腾讯） |
| `category` | `#selectedSecurities` | |
| `documentType` | `#selectedDocType` | 旧档模式 |
| `fromDate` / `toDate` | `YYYYMMDD` | `20260101` |
| `title` | 标题关键词 | |
| `searchType` | 0/1/2 | `1` |
| `t1code` / `t2Gcode` / `t2code` | 见 2.5 | `40000` / `-1` / `40100` |
| `sortByOptions` | `DateTime` / `StockCode` / `StockName` | `DateTime` |
| `sortDir` | `0` 降序 / `1` 升序 | `0` |
| `rowRange` | 已加载条数，点「更多」累加 100 | `100` |

响应 JSON 含 `result`（条目数组字符串）、`recordCnt`、`loadedRecord`、`hasNextRow`、`rowRange`、`lang`。

结果行字段（渲染用，和最新 JSON 不同名）：

| servlet 字段 | 对应最新 JSON |
|---|---|
| `DATE_TIME` | `relTime` |
| `STOCK_CODE` | `stock[].sc` |
| `STOCK_NAME` | `stock[].sn` |
| `TITLE` | `title` |
| `SHORT_TEXT` | `sTxt` / `lTxt` |
| `FILE_LINK` | `webPath` 的绝对形式 |
| `FILE_INFO` | `size` |
| `FILE_TYPE` | `ext`（`PDF` / `HTM`） |
| `DOD_WEB_PATH` | `dodPath` |

### 4.4 股份代号补全

```text
GET https://www1.hkexnews.hk/search/prefix.do?callback=callback&lang=ZH&type=A&name=00700&market=SEHK
```

返回 JSONP：

```js
callback({"more":"1","stockInfo":[{"stockId":7609,"code":"00700","name":"騰訊控股"}]});
```

`name=700`（不足四位）会空返回。搜索提交必须用内部 `stockId`（7609），不能直接填 `00700`。

内部 ID 也可以从在市股票表读：`activestock_sehk_c.json` 的 `i` 就是 `stockId`，`c` 是五位代号，`n` 是简称。腾讯：`{"i":7609,"c":"00700","n":"騰訊控股"}`。

---

## 5. 财报相关代码（本项目默认集）

### 5.1 财务报表 / ESG（t1=40000）

这一级没有分组（`t2Gcode=-1`），四个二级直接挂在一级下。

| t2Code | 繁中 | English | 本项目 |
|---|---|---|---|
| 40100 | 年報 | Annual Report | 默认收录 |
| 40200 | 中期/半年度報告 | Interim/Half-Year Report | 默认收录 |
| 40300 | 季度報告 | Quarterly Report | 默认排除。官方 count 长期为 0 |
| 40400 | 環境、社會及管治資料/報告 | ESG Information/Report | 默认排除 |

### 5.2 公告及通告 / 财务资料（t1=10000, t2G=3）

| t2Code | 繁中 | English | 本项目 |
|---|---|---|---|
| 13100 | 向實體提供墊款 | Advance to an Entity | 排除 |
| 13150 | 董事會召開日期 | Date of Board Meeting | 排除 |
| 13200 | 延遲發表業績公告 | Delay in Results Announcement | 排除 |
| 13250 | 股息或分派 | Dividend or Distribution | 排除 |
| 13251 | 股息或分派（公告表格） | Dividend or Distribution (Announcement Form) | 排除 |
| 13300 | 末期業績 | Final Results | 排除 |
| 13350 | 向聯屬公司提供財務資助及/或作出擔保 | Financial Assistance and/or Guarantee to Affiliated Company | 排除 |
| 13400 | 中期業績 | Interim Results | 排除 |
| 13450 | 資產淨值 | Net Asset Value | 排除（基金/REIT 净值） |
| 13500 | 盈利警告 | Profit Warning | 排除 |
| 13550 | 核數師發出「非標準報告」 | Modified Report by Auditors | 排除 |
| 13600 | 季度業績 | Quarterly Results | 排除 |
| 13650 | 附屬公司的業績 | Results of a Subsidiary | 排除 |
| 13700 | 修訂已刊發初步業績的資料 | Revision of Information in Published Preliminary Results | 排除，可用 `HKEX_T2_CODES` 打开 |
| 13750 | 修正重大錯誤而作出的前期調整 | Prior Period Adjustments due to Correction of Material Errors | 排除 |
| 13800 | 修改已刊發的財務報表及報告 | Revision of Published Financial Statements and Reports | 排除，可用 `HKEX_T2_CODES` 打开 |

### 5.3 看起来像业绩、实际不是财报

杂项（t2G=9）：

| t2Code | 名称 | 说明 |
|---|---|---|
| 19800 | 其他-營運業績最新情況 | Trading update，经营数据快报 |
| 19860 | 海外監管公告-營運業績最新情況 | 同上，A+H 等在海外市场发的版本 |

翌日披露（t1=50000）量很大，不要靠标题关键词剔除，直接按一级码丢掉：

| t2Code | 名称 |
|---|---|
| 50100 | 股份購回 |
| 50200 | 其他 |
| 50300 | 在場內出售庫存股份 |
| 50400 | 修正過往報表 |

### 5.3a 上市文件 / 招股章程（t1=30000）

官方没有单独的「招股说明书」码。IPO 招股文件打在这一级：

| t2Code | 繁中 | English | 本项目 |
|---|---|---|---|
| 30500 | 介紹 | Introduction | 默认收录 |
| 30600 | 發售現有證券 | Offer for Sale | 默认收录 |
| 30700 | 發售以供認購 | Offer for Subscription | 默认收录（全球发售） |
| 30800 | 公開招股 | Open Offer | 排除（再融资） |
| 31100 | 供股 | Rights Issue | 排除（再融资） |
| 31200 | 補充上市文件 | Supplementary Listing Document | 排除 |

### 5.4 默认 Feed 的匹配规则

目标二级集合：

```text
40100, 40200, 30500, 30600, 30700
```

算法：把条目 `t2Code` 按逗号拆分，与目标集合求交，非空即命中。不要再对 `title` / `lTxt` 做正则二次清洗。

覆盖范围可以用环境变量改，不必改代码：

```text
HKEX_T2_CODES=40100,40200,30500,30600,30700,13300
```

---

## 6. 给后续生成器的建议

1. 过滤用 `t1Code` / `t2Code`，展示用 `lTxt`。`lTxt` 会随语言变，代码不会。
2. 需要新类别时，先打开 `tiertwo_c.json` 查官方名称，再写进允许集。不要从快照里的 `lTxt` 猜码。
3. 一条呈交可挂多个 t2，也可挂多只股票（H 股 + 回购股份）。股票过滤按去前导零比较，例如 `00700` 与 `700` 视为同一只。
4. `relTime` 按香港时间解析再转 UTC。
5. 英文快照里会有「中文区已发布」占位标题，做英文 Feed 时要丢弃或回退到繁中 `title`。
6. 最新 JSON 是滚动快照，不是完整历史。超窗数据走标题搜索 servlet，并先把股份代号换成 `stockId`。
7. 创业板在 `lcigem*.json`，不在 `lcisehk*.json`。要覆盖 GEM，再拉一套 `lcigem7relsdc_{n}.json`。
8. 文件类别 `doc_*.json` 只覆盖 2007-06-24 之前，和现在的 t1/t2 不是一张表。

---

## 7. 请求与实现备忘（本项目）

生成器：`generators/finance/hkex_financial_reports.py`
注册名：`hkex_financial_reports`
默认输出：`feeds/feed_hkex_financial_reports.xml`

| 环境变量 | 默认 | 含义 |
|---|---|---|
| `HKEX_T1_CODES` | 空 | 一级码白名单 |
| `HKEX_T2_CODES` | `40100,40200,30500,30600,30700` | 二级码白名单 |
| `HKEX_KEYWORDS` | 空 | 标题/lTxt 关键词，额外收窄 |
| `HKEX_STOCKS` | 空 | 股份代号，去前导零比较 |
| `HKEX_DAYS` | 7 | 相对 `relTime` 的天数窗 |
| `HKEX_MAX_ITEMS` | 50 | RSS 条数上限 |
| `HKEX_MAX_PAGES` | 1 | 最多拉几页最新 JSON |
| `HKEX_DOWNLOAD_PDF` | false | 本地/CI 默认不下载附件 |
| `HKEX_REQUEST_INTERVAL` | 1.0 | 翻页间隔秒 |

运行：

```bash
python scripts/run_single.py hkex_financial_reports
```

---

## 8. 源码与码表链接

| 资源 | URL |
|---|---|
| 最新呈交第 1 页（繁中，近 7 天） | https://www1.hkexnews.hk/ncms/json/eds/lcisehk7relsdc_1.json |
| 最新呈交页面 | https://www1.hkexnews.hk/listedco/listconews/index/lci.html |
| 标题搜索页 | https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=ZH |
| 搜索配置（繁中） | https://www1.hkexnews.hk/ncms/eds/titlesearch/config_c.js |
| 搜索配置（英文） | https://www1.hkexnews.hk/ncms/eds/titlesearch/config.js |
| 一级码表 | https://www1.hkexnews.hk/ncms/script/eds/tierone_c.json |
| 二级码表 | https://www1.hkexnews.hk/ncms/script/eds/tiertwo_c.json |
| 二级分组 | https://www1.hkexnews.hk/ncms/script/eds/tiertwogrp_c.json |
| 文件类别（2007 前） | https://www1.hkexnews.hk/ncms/script/eds/doc_c.json |
| 在市股票 | https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_c.json |
| 最新 JSON 拼装逻辑 | https://www1.hkexnews.hk/ncms/js/lci.js |
| 搜索表单逻辑 | https://www1.hkexnews.hk/ncms/js/titlesearch.js |
| 搜索结果 servlet 调用 | https://www1.hkexnews.hk/ncms/js/titlesearch_research.js |

本地规格：

- 需求：当前工作区 `/workspace/.monkeycode/specs/2026-10-28-hkex-financial-reports/requirements.md`
- 设计：当前工作区 `/workspace/.monkeycode/specs/2026-10-28-hkex-financial-reports/design.md`
