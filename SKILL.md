---
name: fulltext-retrieval
description: Batch download open-access PDFs by DOI using legitimate OA APIs (Unpaywall, PMC, OpenAlex, Crossref). Optional PDF→Markdown conversion for token-efficient LLM analysis.
triggers: PDF download, fulltext retrieval, open access PDF, batch download papers, meta-analysis PDF, PDF to markdown, convert PDF
tools: Read, Write, Edit, Bash, Grep, Glob
model: inherit
---

# Fulltext Retrieval Skill

Batch download open-access full-text PDFs from a DOI list using legitimate OA APIs only.

## Pipeline

```
DOI → arXiv (10.48550/arXiv.* DOIs) → Unpaywall → PMC (Europe PMC / OA FTP / web) → OpenAlex → Crossref → landing page
```

Each DOI goes through these sources in order until a valid PDF (≥10 KB, `%PDF-` header) is found. arXiv DOIs (`10.48550/arXiv.2401.01234`, version suffixes, old-style `hep-th/9901001`, or a bare `arXiv:` id) resolve directly to the arXiv PDF first.

## Quick Start

```bash
# Prepare a DOI list (one per line)
cat > dois.txt << 'EOF'
10.1007/s00330-010-1783-x
10.1002/mp.12524
10.1148/radiol.13131265
EOF

# Run
python fetch_oa.py dois.txt --output pdfs/ --email your@email.com

# Verbose mode for debugging
python fetch_oa.py dois.txt -o pdfs/ -e your@email.com --verbose
```

## Input Formats

**Plain text** — one DOI per line:
```
10.1007/s00330-010-1783-x
10.1002/mp.12524
```

**TSV / CSV with header** — must contain a `DOI` column; optional `PMID` and `Title` columns:
```tsv
ID	Title	DOI	PMID	Year
1	Some paper	10.1007/s00330-010-1783-x	20628747	2010
```

**Markdown table** — a pipe table with a `DOI` column also works:
```markdown
| DOI | PMID | Title |
|-----|------|-------|
| 10.1007/s00330-010-1783-x | 20628747 | Some paper |
```

When a PMID is available, the PMC lookup is more reliable (PMID → PMCID conversion). When a `Title` column is present, downloaded PDFs get a best-effort title cross-check (see *Retrieval report* below).

## PMC Download (JS-Challenge Resistant)

PMC web pages may block automated downloads with JavaScript proof-of-work challenges. This tool uses three fallback methods:

### Method A: Europe PMC REST API (most reliable)

```bash
PMCID="PMC9733600"
curl -sLo output.pdf \
  "https://europepmc.org/backend/ptpmcrender.fcgi?accid=${PMCID}&blobtype=pdf"
```

### Method B: PMC OA FTP Service

```bash
curl -s "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=${PMCID}" | \
    grep -oE 'href="[^"]*\.pdf"' | head -1 | \
    sed 's/href="//;s/"//' | xargs curl -sLo output.pdf
```

### DOI/PMID → PMCID Conversion

```bash
# Works with both DOI and PMID
curl -s "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids=${DOI}&format=json" | \
    python3 -c "import sys,json; print(json.load(sys.stdin)['records'][0].get('pmcid',''))"
```

## Output

- PDFs saved as `{DOI_safe}.pdf` (slashes replaced with underscores)
- `pdfs/retrieval_report.json` — structured per-DOI report (see below)
- `manual_needed.txt` — DOIs that could not be retrieved via OA
- Summary with arXiv/OA/PMC/fail/skip counts

## Retrieval report (`--report`)

Every run writes a structured report (default `<output>/retrieval_report.json`,
override with `--report PATH`):

```json
{
  "schema_version": 1,
  "generated_by": "fetch_oa.py",
  "counts": {"total": 10, "retrieved": 6, "not_retrieved": 4, "title_mismatch": 1},
  "items": [
    {"doi": "10.1007/...", "pmid": "20628747", "title": "...",
     "status": "oa", "source": "unpaywall", "file": "10.1007_....pdf",
     "size_bytes": 482113, "title_match": "match"}
  ]
}
```

- `status` ∈ `arxiv | oa | pmc | skip | fail`; `source` names the resolver that succeeded.
- `title_match` ∈ `match | mismatch | unavailable` (tri-state). It is **best-effort**:
  it needs a `Title` column **and** `pdftotext` (poppler). When either is missing it is
  `unavailable`; a `mismatch` is **flagged** for review and **never** auto-rejects a PDF
  (guards against a publisher serving a wrong/redirect PDF that still passes the `%PDF-` check).

## Attach PDFs into Zotero ("Find Available PDF")

OA-only resolvers miss paywalled-but-licensed papers. To attach full text **inside
Zotero** at a much higher yield, use `references/find_available_pdf.js` — a user-run
snippet for Zotero's *Tools → Developer → Run JavaScript*. It triggers Zotero's own
`addAvailablePDF` / `addAvailablePDFs` and therefore reuses **your** OpenURL resolver /
institutional proxy config; **no credentials, proxy hosts, or institutional identifiers
are hard-coded or leave your Zotero client**. The no-code equivalent is right-click →
"Find Available PDF".

This path is **user-initiated** and depends on your live Zotero session, so its results
are recorded manually (not reproducible CI evidence). `/lit-sync` Phase 2.7 orchestrates
both routes (disk OA via this script + in-library via the snippet) and reconciles them in
a report.

## Requirements

- Python 3.10+ (stdlib only, no pip dependencies)
- Contact email (required by Unpaywall Terms of Service)

## API Policies

| Source | Rate Limit | Notes |
|--------|-----------|-------|
| Unpaywall | 100 req/sec | Email required |
| NCBI PMC | 3 req/sec without API key | Add `&api_key=` for higher limits |
| OpenAlex | 100k req/day | Polite pool with email in User-Agent |
| Crossref | 50 req/sec with email | Plus service with `mailto:` in UA |
| Europe PMC | No documented limit | Be polite, ≤1 req/sec recommended |

The script uses 0.3–0.5 second delays between requests.

## PDF → Markdown Conversion (Optional)

After downloading PDFs, convert them to LLM-friendly Markdown for token-efficient repeated analysis. Uses [pymupdf4llm](https://github.com/pymupdf/RAG) — optimized for academic papers with two-column layout handling and table preservation.

### Quick Start

```bash
# Install (one-time)
pip install pymupdf4llm

# Convert all PDFs in a directory
python pdf_to_md.py pdfs/

# Convert with verbose output
python pdf_to_md.py pdfs/ -v

# Custom output directory
python pdf_to_md.py pdfs/ -o markdown/

# First 10 pages only (useful for long supplements)
python pdf_to_md.py pdfs/ --pages 0-9

# Overwrite existing conversions
python pdf_to_md.py pdfs/ --force
```

### Combined Workflow

```bash
# Step 1: Download PDFs
python fetch_oa.py dois.txt -o pdfs/ -e your@email.com

# Step 2: Convert to Markdown (only successful downloads)
python pdf_to_md.py pdfs/ -v
```

After conversion, `.md` files sit alongside `.pdf` files. Claude Code can then use `Read` for full content or `Grep` for targeted extraction — significantly more token-efficient than re-reading PDFs.

### When to Convert

| Scenario | Recommendation |
|----------|---------------|
| Screening/triage (read once) | Skip — read PDF directly |
| Data extraction from k≥5 studies | Convert — repeated reads save tokens |
| Meta-analysis full pipeline | Convert — papers referenced across multiple phases |
| Single paper deep review | Optional — marginal benefit |

### Academic Paper Defaults

- **Images**: Skipped (saves tokens; figures referenced by caption text)
- **Tables**: `lines_strict` strategy (preserves grid-line tables accurately)
- **Layout**: Two-column academic layout handled automatically
- **Headers/footers**: Removed by pymupdf4llm

### Dependency Note

`pdf_to_md.py` requires [pymupdf4llm](https://pypi.org/project/pymupdf4llm/) (AGPL-3.0). This is an **optional** dependency — `fetch_oa.py` remains stdlib-only with zero external dependencies. The AGPL license applies to pymupdf4llm itself, not to this skill.

## ⚠️ Field-Tested Retrieval Playbook (2026-08-30 实测)

**The PDF cascade above fails on major clinical journals.** Measured on 4
high-impact stroke trials: `Success: 0%` — AHA/Stroke, BMJ/JNNP and Neurology all
return **HTTP 403** even with a browser UA; `europepmc.org/backend/ptpmcrender.fcgi`
returns **HTTP 520**; PMC OA FTP returns 404. Use the channels below instead.

### Channel status (all empirically tested)

| Channel | Status | Notes |
|---|---|---|
| **Europe PMC `/fullTextXML`** | ✅ **primary** | JATS full text, no key, no email. 100% on OA records |
| **Europe PMC `/search`** | ✅ | Use `HAS_FT:Y` / `OPEN_ACCESS:Y`. See syntax table |
| NCBI ID Converter | ✅ | DOI→PMCID fallback for the "is it available?" decision |
| Unpaywall / OpenAlex / S2 | ✅ | **Availability verdict only** — they decide, they don't deliver |
| OpenAlex citation graph | ✅ | The paywall workaround. See §Paywalled papers |
| **Clinical trial registries** | ✅ **endpoint data** | `resultsSection` — **no publication bias**. See §Trial registries |
| bioRxiv / medRxiv API | ✅ metadata | Works; PDF fetch is 429-prone, back off and retry |
| DOAJ / OpenAIRE / Zenodo | ✅ discovery | Niche; useful for institutional-repository deposits |
| CORE **search** | ⚠️ unstable | Hit-or-miss: 4.8M hits one call, 429/500/timeout the next |
| CORE **download** | ❌ | HTTP 400 — requires an API key |
| Publisher PDF direct | ❌ | 403 across AHA / BMJ / Elsevier / Wolters-Kluwer |
| PMC OA FTP / ptpmcrender | ❌ | 404 / 520 |
| Europe PMC `FULL_TEXT:` field | ❌ | **Always returns `hitCount: 0`** on this API version |

### Decision order

Run these in order; stop at the first one that answers the question.

| # | Route | Cost | Latency | Use when |
|---|---|---|---|---|
| 1 | **Trial registry** | 0 | instant | Question is "did this trial hit its endpoint?" |
| 2 | OA full text (Europe PMC) | 0 | instant | Paper exists and is open access |
| 3 | Citation-chain secondary source | 0 | instant | Paywalled; need N / dose / endpoint values |
| 4 | Author request | 0 | 1–4 weeks | Not urgent |
| 5 | NSTL / interlibrary loan | ¥20–30 | 1–3 days | Need the actual PDF text |
| 6 | Publisher single-article purchase | $30–40 | instant | Urgent, must have verbatim text |
| 7 | Institutional subscription / VPN | 0 | instant | Your organisation has access |

Route 1 is the one people forget. Route 3 covers most paywalled papers, because
meta-analyses tabulate the original trial's numbers in their own open-access
Table 1 — which means **routes 5–6 are rarely needed just to get the data**.

**The `bronze` OA trap.** OpenAlex may report `is_oa=true` with
`oa_status=bronze` — meaning the publisher made it free on their own site, without
an open licence. The `best_oa_location.pdf_url` then points at a publisher URL that
returns **403 to curl** (bot filtering) or fails TLS entirely from mainland China
(e.g. AHA: `SSL connect error`, curl exit 35). That is **not a paywall** — it is
anti-scraping plus network path. Route: institutional VPN, or fall back to route 3.
Do not conclude "unavailable" and do not attempt to defeat the bot filter.

### Do not declare "no results" too early

The most expensive error in this workflow is concluding *"it does not exist"*
before exhausting the search. It happened in practice on 2026-08-30 with
NSI-566: searching the product code returned 6 hits, the first two were spinal
cord injury, and "no stroke publication" was wrongly concluded — when the stroke
Phase 1 result was sitting at hit #6.

Three rules that prevent it:

1. **Scan every hit, not the first few.** With a product/compound code, skim the
   full result list before inferring an indication is unpublished. Two papers
   about one indication say nothing about another.
2. **Registry-number reverse lookup often returns nothing.** Many papers never
   put the NCT/ChiCTR ID in the abstract, so `search "NCT03296618"` yields 0 even
   when the trial is published. Fall back to **author surname + indication** and
   **intervention name + indication**.
3. **"No results posted" on the registry ≠ "unpublished".** Check PubMed
   separately. Conversely, `COMPLETED` + `hasResults=True` + no paper is the real
   signature of a swept-under-the-rug negative result.

Corollary for paywalled work: before concluding "not obtainable", run the
registry route, the citation-chain route **and** an author-surname search.
Each uses a different index and they fail independently.

### Step 1 — Search (use the verified syntax)

```bash
python references/epmc_search.py search \
  'HAS_FT:Y AND OPEN_ACCESS:Y AND "neural stem cell" AND "chronic stroke"' -n 20
```

| Query fragment | Result |
|---|---|
| `HAS_FT:Y` | ✅ works — restrict to records with full text |
| `OPEN_ACCESS:Y` | ✅ works |
| `JOURNAL:"..."` | ✅ works (0 hits + `OPEN_ACCESS:Y` ⇒ that journal has no OA) |
| `FULL_TEXT:"..."` | ❌ **broken** — silently returns 0 hits. Never use it |

The script prints a result table, then lists the PMCIDs that are actually
downloadable. `harvest` runs search + download in one shot:

```bash
python references/epmc_search.py harvest '<query>' -n 20 -o xml/
```

### Step 2 — Download full text as JATS XML

```bash
python references/epmc_search.py fetch PMC7147186 PMC11373674 -o xml/
```

Validate: a real hit is **≥10 KB containing a `<article` element**. Europe PMC
returns two legal shapes — check for `<article`, **not** for `<!DOCTYPE`:

```
<!DOCTYPE article PUBLIC "-//NLM//DTD JATS..."          (with DTD)
<?xml version="1.0" encoding="UTF-8"?><article ...>     (no DTD — equally valid)
```

Matching only the doctype silently discards ~40% of valid responses (verified:
a 162 KB and a 291 KB full text were both thrown away that way). A 0-byte or
16-byte body (the literal string `error`) means embargo / abstract-only deposit
— **treat as permanently unavailable, do not retry.**

### Step 3 — Convert to readable text

```bash
python references/jats_to_text.py xml/PMC7147186.xml > paper.txt
```

Emits `## Section` headings, body paragraphs (>25 chars) and `[TABLE n]` captions.
Typical yield: 20–30 KB of clean text per paper, versus a full PDF read.

### DOI → PMCID fallback

When a DOI is absent from Europe PMC, confirm with NCBI before giving up:

```bash
curl -s "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids=<DOI>&format=json"
```

An empty `pmcid` here **plus** `is_oa=false` in Unpaywall **plus** no PMCID in
Europe PMC is a triple-confirmed paywall — go straight to the citation route.

### Trial registries — when the paper does not exist

**Registries are a better source than journals for endpoint data.** FDAAA 801 and
the WHO ICTRP standard require all pre-specified endpoints to be posted; journals
have no such rule. **Negative trials are routinely never published**, so the
registry is often the *only* place a failed endpoint is on record — and it is
free, authoritative and instant.

**Use it when:** the paper is paywalled *and* has no OA secondary source — or,
better, **before** hunting for the paper at all when the question is "did this
trial hit its endpoint?".

```bash
python references/ctr_fetch.py NCT02448641            # primary endpoints
python references/ctr_fetch.py NCT02448641 --all       # + secondary endpoints
python references/ctr_fetch.py NCT02448641 --json raw.json
```

The script prints status, phase, N, results-posted date, arm titles with
denominators, and per-arm counts **with percentages computed**, e.g.:

```
[PRIMARY] Proportion of Subjects Whose FMMS Improved by >=10 Points at Month 6
  OG000    SB623 Implant (2.5M)   (n=55)
  OG001    SB623 Implant (5.0M)   (n=56)
  OG002    Sham Control           (n=52)
  Responder      OG000=7 (12.7%)  |  OG001=9 (16.1%)  |  OG002=7 (13.5%)
```

**Reading the output — three checks that catch most misreadings:**

1. Compare active arms against the **control** arm, never against zero.
2. Look at the control arm's own response rate. A high sham response invalidates
   every single-arm "improvement" claim in the same indication.
3. If the trial completed years ago and no paper exists, the registry **is** the
   definitive record — say so explicitly when citing, and cite the NCT ID.

**Detecting "there is no paper":** search PubMed for the product code. If every
hit is preclinical or a different indication, the trial is unpublished. Confirm
with `hasResults` on the registry — `COMPLETED` + `hasResults=True` + no paper is
the signature of a failed endpoint.

Worked example (2026-08-30): searching `SB623` returns 12 papers, all preclinical
or TBI — the chronic-stroke Phase 2b was **never published**. The registry shows
why: low dose 12.7% vs sham 13.5%. No amount of paywall bypass would have found
that paper, because it does not exist.

Other registries with the same principle: ChiCTR (chictr.org.cn), WHO ICTRP,
EU CTIS, jRCT.

### Preprints (bioRxiv / medRxiv)

```bash
curl -s "https://api.biorxiv.org/details/biorxiv/2025-06-01/2025-06-02/0"      # metadata
curl -sL -o pp.pdf "https://www.biorxiv.org/content/<doi>v<version>.full.pdf"  # full text
```

Metadata is reliable; the PDF endpoint rate-limits (429) — retry with backoff.
medRxiv is the same API shape at `api.medrxiv.org` / `www.medrxiv.org`.

### Paywalled papers: the citation-chain route (verified end-to-end)

When Step 1 shows no OA copy, do **not** give up:

1. `https://api.openalex.org/works/doi:<DOI>` → take the short work id.
2. `https://api.openalex.org/works?filter=cites:<id>,is_oa:true&sort=cited_by_count:desc&select=id,doi,title,publication_year,primary_location`
3. Filter titles for `meta|systematic|efficacy and safety`, then run Steps 1–3 on
   those DOIs. Meta-analyses tabulate the paywalled trial's **N, dose, time window,
   and endpoint numbers** in their own (open-access) Table 1.

Verified: for Lancet Neurol 2023 IBIS (no OA copy in Unpaywall, OpenAlex, S2 or
Europe PMC) this surfaced **24 OA citing papers**, of which ≥3 were full-text
meta-analyses that tabulate IBIS directly. Cite the meta-analysis as `[二次来源]`
and downweight one evidence tier.

### Rate limits

| Source | Limit | Handling |
|---|---|---|
| Europe PMC | none documented | 0.4 s sleep is enough |
| NCBI PMC | 3/s without key | 0.4 s sleep |
| Semantic Scholar | strict, no key | 429 is common; sleep 1 s+, don't parallelise |
| CORE | key-gated | expect 429/500 on anonymous calls |

## Limitations

- Only retrieves **open-access** articles. Paywalled articles require institutional access.
- Landing page scraping may fail on publisher-specific JavaScript-heavy pages.
- Some recent articles may not yet be indexed by OA sources.
- PDF→Markdown quality depends on the PDF's text layer. Scanned-only PDFs may produce poor output.

## Anti-Hallucination

- **Never fabricate file paths, URLs, DOIs, or package names.** Verify existence before recommending.
- **Never invent journal metadata, impact factors, or submission policies** without verification at the journal's website.
- If a tool, package, or resource does not exist or you are unsure, say so explicitly rather than guessing.
