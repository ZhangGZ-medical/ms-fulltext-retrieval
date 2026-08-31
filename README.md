# ms-fulltext-retrieval

按 DOI 批量下载**开放获取**全文的 PDF，使用合法 OA API 级联。**可选**将 PDF 转为 Markdown 以便 LLM 分析。

> 本仓库在原始 `medsci-skills` 版本基础上，补充了 2026-08-30 实地验证后的修正与扩展（见下文「实地验证补丁」）。PDF 直连通道在多数临床期刊上已失效，实际主力是 Europe PMC 的 JATS 全文 XML 接口。

## 能力

| 通道 | 状态 | 说明 |
|---|---|---|
| **Europe PMC `/fullTextXML`** | 主力 | JATS 全文，免 key 免邮箱，OA 记录 100% 命中 |
| **Europe PMC `/search`** | 可用 | 用 `HAS_FT:Y` / `OPEN_ACCESS:Y` 过滤 |
| **NCBI ID Converter** | 可用 | DOI → PMCID，用于"是否可得"判定 |
| **Unpaywall / OpenAlex / S2** | 可用 | 仅判定可得性，不投递文件 |
| **OpenAlex 引文网络** | 可用 | 付费墙文献的绕行取数路径 |
| **ClinicalTrials.gov** | 可用 | 注册库终点原始数据 |
| **bioRxiv / medRxiv** | 可用（元数据） | PDF 抓取易 429，需退避 |
| **DOI / OpenAlex / Crossref / landing page** | 不稳定 | 见下 |
| **出版商 PDF 直连** | 失效 | AHA / BMJ / Elsevier / Wolters 均 403 |
| **PMC ptpmcrender / OA FTP** | 失效 | 520 / 404 |

## 结构

```
ms-fulltext-retrieval/
├── SKILL.md                       # 管线 + 实地验证手册
├── skill.yml
├── fetch_oa.py                    # OA 级联下载（stdlib only）
├── pdf_to_md.py                   # PDF → Markdown（需 pymupdf4llm）
├── tests/test_pdf_to_md.py
├── fetch_oa_report_challenge/     # 离线确定性校验卡
└── references/
    ├── epmc_search.py             # 检索 / 下载 JATS / 一键 harvest
    ├── jats_to_text.py            # JATS XML → 纯文本
    ├── ctr_fetch.py               # ClinicalTrials.gov 结果取数
    └── find_available_pdf.js      # Zotero 内"查找可用 PDF"片段
```

## 用法

### JATS 全文（推荐）

```bash
PY="python"

# 1. 检索
"$PY" references/epmc_search.py search \
  'HAS_FT:Y AND OPEN_ACCESS:Y AND "neural stem cell" AND "chronic stroke"' -n 20

# 2. 下载
"$PY" references/epmc_search.py fetch PMC7147186 PMC11373674 -o xml/

# 3. 转文本
"$PY" references/jats_to_text.py xml/PMC7147186.xml > paper.txt

# 一键：检索 + 下载
"$PY" references/epmc_search.py harvest '<query>' -n 20 -o xml/
```

**校验**：真命中 ≥10 KB 且含 `<article` 元素。Europe PMC 返回两种合法格式——
`<!DOCTYPE article ...>`（带 DTD）与 `<?xml version="1.0"?><article ...>`（无 DTD）。
**只匹配 doctype 会静默丢弃约 40% 的有效响应**。0 字节或 16 字节（字面量 `error`）表示 embargo / 仅摘要存档，视为永久不可得，不要重试。

### 注册库取数

```bash
"$PY" references/ctr_fetch.py NCT02448641 --all
```

输出 N、分期、状态、结果上传日、各组计数，并自动计算百分比。

### 传统 PDF 级联

```bash
"$PY" fetch_oa.py dois.txt -o pdfs/ -e your@email.com --verbose
```

## 实地验证补丁（2026-08-30）

原始 PDF 级联在 4 个高影响力卒中试验上实测 **0/4 成功**（AHA/Stroke、BMJ/JNNP、Neurology 均 403；Europe PMC ptpmcrender 返回 520；PMC OA FTP 返回 404）。因此补充：

1. **JATS 三步法**：检索 → 下载 XML → 转文本。比 PDF 更精确（无 OCR 误差、表格结构化）。
2. **付费墙绕行（引用链）**：用 OpenAlex 的 `cites:<id>,is_oa:true` 找引用该文献的 OA 荟萃分析，其 Table 1 常直接表格化原试验的 N / 剂量 / 时间窗 / 终点值。引用时标 `[二次来源]` 并降一档权重。
3. **注册库作为一级数据源**：试验注册库必须报告全部预设终点，**阴性试验常被发表偏倚吞没**，注册库往往是唯一记录。
4. **检索穷尽性三原则**：`FULL_TEXT:` 字段在本 API 版本恒返回 0，不可用；用产品代号检索后必须逐篇核对命中结果，不可因前几条属其他适应症就推断该适应症无发表；NCT 号反查常为 0，须改用「作者名 + 适应症」定向检索。
5. **bronze OA 陷阱**：`oa_status=bronze` 表示出版商自家站点免费但无开放许可，其 `pdf_url` 对 curl 返回 403 或国内直连 TLS 失败（curl exit 35）。这是反爬 + 网络路径问题，**不是付费墙**，应走机构 VPN 或回退二次来源。

## 依赖

- Python 3.10+（`fetch_oa.py` 与 `references/` 下脚本为 stdlib only）
- `pdf_to_md.py` 需 `pymupdf4llm`（AGPL-3.0，可选）
- 网络：需访问 `www.ebi.ac.uk`、`clinicaltrials.gov`

## 来源

属于 `medsci-skills` 技能套件（`/fulltext-retrieval` 模块），`/search-lit` 的 Phase 5 委托至此。
