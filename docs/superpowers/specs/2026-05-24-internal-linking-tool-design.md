# Internal Linking Opportunity Tool — Design Spec

**Date:** 2026-05-24
**Status:** Approved
**Type:** Greenfield Web Application

---

## 1. Overview

A local-first web tool that identifies internal linking opportunities by cross-referencing Screaming Frog crawl data with Google Search Console query data. For a given target URL, the tool finds pages across the site that mention relevant keywords but don't yet link to the target, then suggests anchor text based on real search query data.

### Core Value Proposition
- **Eliminates manual site:search and spreadsheet work** — programmatic keyword matching across the entire crawl
- **Prioritizes by impact** — opportunities ranked by Link Authority × organic traffic
- **Smart anchor suggestions** — GSC impression-weighted anchor text prevents over-optimization
- **Runs locally** — no cloud dependency, works with existing Screaming Frog installation

---

## 2. Architecture

### 2.1 Tech Stack
- **Backend:** Python (FastAPI) running locally on localhost
- **Frontend:** HTML/CSS/JavaScript served by FastAPI. Use HTMX for SSE polling and Alpine.js for reactive table interactions (sorting, filtering, row expansion). Keeps the stack lightweight without a full SPA framework.
- **External Dependencies:**
  - Screaming Frog SEO Spider CLI (local installation)
  - Google Search Console API (OAuth 2.0)
- **Key Libraries:** `fastapi`, `google-api-python-client`, `pandas`, `beautifulsoup4`, `httpx`, `uvicorn`

### 2.2 Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    User's Machine                        │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ Browser  │───▶│ FastAPI       │───▶│ SF CLI        │  │
│  │ (local-  │    │ Server        │    │ (local proc)  │  │
│  │  host)   │◀───│               │◀───│               │  │
│  └──────────┘    │  ┌─────────┐  │    └───────────────┘  │
│                  │  │ Match    │  │                      │
│                  │  │ Engine   │  │    ┌───────────────┐  │
│                  │  └─────────┘  │───▶│ GSC API       │  │
│                  │  ┌─────────┐  │    │ (remote)      │  │
│                  │  │ Anchor   │  │    └───────────────┘  │
│                  │  │ Engine   │  │                      │
│                  │  └─────────┘  │    ┌───────────────┐  │
│                  │  ┌─────────┐  │───▶│ Source Pages  │  │
│                  │  │ Page     │  │    │ (HTTP fetch)  │  │
│                  │  │ Fetcher  │  │    └───────────────┘  │
│                  │  └─────────┘  │                      │
│                  └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Core Components

| Component | Responsibility | Dependencies |
|---|---|---|
| **SF CLI Manager** | Detect SF installation, list saved crawls, start headless crawls, poll status, export CSV data. Handle GUI lock detection. | SF CLI binary on user's machine |
| **GSC Client** | OAuth 2.0 flow (localhost redirect), query Search Analytics API, paginate results (up to 25K rows/call), cache results locally | Google API, user's Google account |
| **CSV Parser** | Parse Screaming Frog `internal_all.csv` export. Extract URLs, Link Score, Unique Inlinks, Outlinks, status codes. Validate schema. | pandas |
| **Page Fetcher** | Async HTTP fetch of source page content. Extract readable text + all outbound links. Respect rate limits and timeouts. | httpx, beautifulsoup4 |
| **Match Engine** | Core matching logic: for each source page, check if any GSC keyword appears in page text AND the target URL is NOT in the page's outlinks. Score by Link Authority × GSC clicks. Group results by source URL. | CSV Parser, Page Fetcher, GSC Client |
| **Anchor Text Engine** | Build impression-weighted anchor text distribution from GSC query data. For each match, suggest primary anchor (highest impression) and variations. | GSC Client |
| **FastAPI Server** | Serve frontend static files, REST API endpoints, SSE progress streaming, CSV export endpoint | uvicorn |

### 2.4 Data Flow

1. User enters target URL in browser (localhost)
2. Server queries SF CLI: list available crawls or start new one
3. Server exports `internal_all.csv` from selected SF crawl
4. CSV Parser extracts: source URLs, Link Scores, outlinks, status codes
5. GSC Client fetches queries for target URL (impressions, clicks, CTR)
6. Page Fetcher pulls rendered text + outlinks from each source URL (async, batched)
7. Match Engine: for each source URL, check keyword presence AND link exclusion, group by URL
8. Anchor Engine: compute impression-weighted anchor suggestions per match
9. Results streamed to frontend via SSE, rendered as grouped opportunity table

---

## 3. User Experience

### 3.1 Input Flow (4 Steps)

| Step | Screen | User Action |
|---|---|---|
| **1. Target URL** | Text input + "Analyze" button | Paste the URL to build links to |
| **2. Crawl Source** | Two-panel: "Use Existing Crawl" (dropdown of saved crawls) or "Start New Crawl" (with config options) | Select or trigger crawl |
| **3. Progress** | Progress bar with phase labels (GSC fetch → CSV parse → Page scan → Matching). Cancel button. | Wait or cancel |
| **4. Results** | Grouped opportunity dashboard | Explore, filter, export |

### 3.2 Results Dashboard

**Summary Bar:** Source pages with opportunities | Total anchor options | Pages scanned | GSC keywords used

**Table Columns:**
- **Page to Add Link To** — clickable URL (opens in new tab)
- **Link Authority** — color-coded badge (green >80, orange 50-80, red <50)
- **Organic Clicks (90d)** — from GSC integration
- **Anchors** — count badge of keyword matches on this page
- **Best Anchor Text** — highest-impression anchor suggestion

**Row Expansion:** Click a row to see all anchor options with:
- Keyword matched, anchor text suggestion, GSC impression share percentage
- Surrounding text context (sentence containing the keyword)
- All options ranked by impression share

**Interactions:**
- Sort by: Priority (authority × clicks), Clicks, Match count
- Filter by: Minimum Link Authority threshold, keyword text search
- Export: Download filtered results as CSV

### 3.3 Grouping Logic

Multiple keyword matches on the same source URL are collapsed into a single row. The "Anchors" column shows the count. Expanded detail shows all options. This means one CMS edit session per page, not per keyword.

---

## 4. API Design

### 4.1 Endpoints

| Method | Endpoint | Purpose | Response |
|---|---|---|---|
| `GET` | `/api/health` | System readiness check | `{ sf_installed, gsc_configured, sf_path }` |
| `GET` | `/api/crawls` | List saved SF crawls | `[{ id, name, date, url_count }]` |
| `POST` | `/api/crawls` | Start new headless crawl | `{ crawl_id, status: "running" }` |
| `GET` | `/api/crawls/{id}/status` | Poll crawl progress | `{ phase, percent, urls_crawled }` |
| `POST` | `/api/analyze` | Begin analysis | `{ analysis_id, status: "queued" }` |
| `GET` | `/api/analyze/{id}/stream` | SSE progress events | `event: phase=X, detail=Y, percent=Z` |
| `GET` | `/api/analyze/{id}/results` | Paginated results | `{ opportunities[], total, page }` |
| `GET` | `/api/analyze/{id}/results?sort=priority&min_authority=60&q=keyword` | Filtered results | Same shape, filtered |
| `GET` | `/api/analyze/{id}/export` | CSV download | `text/csv` |
| `GET` | `/api/gsc/auth` | Initiate OAuth | Redirect to Google |
| `GET` | `/api/gsc/callback` | OAuth callback | Redirect to app |

### 4.2 Result Schema

```json
{
  "opportunities": [
    {
      "source_url": "/blog/solar-panel-guide-2024",
      "link_authority": 94,
      "organic_clicks_90d": 1240,
      "match_count": 3,
      "best_anchor": "renewable energy solutions",
      "matches": [
        {
          "keyword": "renewable energy solutions",
          "anchor_text": "renewable energy solutions",
          "impression_share": 0.40,
          "context": "...the future of renewable energy solutions depends on..."
        },
        {
          "keyword": "sustainable power",
          "anchor_text": "sustainable power sources",
          "impression_share": 0.25,
          "context": "...shifting toward sustainable power generation requires..."
        }
      ]
    }
  ],
  "meta": {
    "total_opportunities": 32,
    "total_anchor_options": 47,
    "pages_scanned": 1240,
    "gsc_keywords": 312,
    "page": 1,
    "per_page": 100
  }
}
```

---

## 5. Error Handling & Graceful Degradation

### 5.1 Graceful Degradation Principle

The tool has two independent pipelines. If one fails, the other still produces useful results:

```
SF Crawl → Matching (always runs, finds unlinked mentions)
    +
GSC → Anchor Suggestions (enhances with impression-weighted anchor text)
    =
Full Results (both) or Partial Results (either alone)
```

### 5.2 Error States

| Error | Severity | Behavior |
|---|---|---|
| SF not installed / wrong path | **Fatal** | Health check on startup. Settings page to configure path. Block analysis until resolved. |
| SF GUI is open (database locked) | **Fatal** | Detected automatically. Clear message: "Close Screaming Frog to continue." |
| No saved crawls | **Guidance** | Show "Start New Crawl" option prominently. Not an error. |
| Crawl timeout | **Recoverable** | Configurable timeout (default 30 min). Offer cancel + retry in GUI. |
| GSC auth failure / no permissions | **Non-blocking** | Analysis continues without anchor suggestions. "Reconnect in Settings" prompt. |
| GSC quota exceeded (50K rows/day) | **Non-blocking** | Use cached data if fresh (<7 days). Fall back to crawl-only matching. |
| Target URL not in crawl data | **Fatal** | "URL not found in crawl. May be orphaned or blocked. Try a fresh crawl." |
| Zero opportunities found | **Informational** | "No unlinked mentions found. Page may be well-linked or keywords don't match content." |
| Page fetch failures (timeouts, 404s) | **Partial** | Continue with successful fetches. Show count of failed pages. Offer retry. |
| Malformed CSV export | **Fatal** | Fail fast. Show expected vs found columns. "Re-export from Screaming Frog." |

### 5.3 Caching Strategy
- GSC query results cached per target URL, TTL: 7 days
- SF crawl exports cached per crawl ID until a new crawl is run
- Page fetch results not cached (content changes)

---

## 6. Matching Algorithm

### 6.1 Match Conditions
A source page is an opportunity if it satisfies BOTH:
0. **Eligible:** The source page has a 200 status code, is not a redirect, and is not canonicalized to another URL (matching Screaming Frog's Link Score eligibility criteria).
1. **Contains:** At least one GSC keyword appears in the page's rendered text (case-insensitive, whole-word-aware) (where "whole-word-aware" means the keyword must be surrounded by word boundaries: whitespace, punctuation, or start/end of the text being searched)
2. **Does Not Contain:** The target URL's path (relative URL, e.g. `/your-target-page/`) does NOT appear as an `href` value in the source page's outbound HTML links. Checked in raw HTML, not rendered text, to catch both relative and absolute link formats.

### 6.2 Scoring Formula
```
Priority Score = Link Authority × log(Organic Clicks + 1)
```
Log scale on clicks prevents a single high-traffic page from dominating. Link Authority (0-100) is the primary weight.

### 6.3 Anchor Text Distribution
Anchor suggestions follow the GSC impression distribution to prevent over-optimization:
- If "renewable energy" = 40% of target page impressions → suggest as anchor for ~40% of opportunities
- Remaining opportunities use secondary/long-tail variations
- Exact-match keywords prioritized for high-authority source pages

---

## 7. Testing Strategy

| Layer | What | How |
|---|---|---|
| **Unit** | Match Engine, Anchor Engine, CSV Parser | `pytest`. Pure logic, no external deps. Test edge cases: empty input, single match, 100% impression keyword. |
| **Integration** | SF CLI wrapper, GSC client, Page Fetcher | Mock external processes. `responses` for HTTP. Sample SF export files for CLI parsing tests. Test every error state. |
| **Pipeline** | End-to-end: URL → crawl → GSC → match → results. Degradation when GSC down. | Recorded fixtures: real SF export CSV + real GSC JSON response. Deterministic replay. Verify output shape. |
| **Manual** | OAuth flow, GUI lock detection, real crawl on test site | Pre-release checklist. Can't fully automate OAuth or GUI interaction. |

**Fixture files** (versioned in repo): `tests/fixtures/sample_crawl.csv`, `tests/fixtures/gsc_response.json`

---

## 8. Scope Boundaries

### IN Scope (v1)
- Single target URL analysis
- Screaming Frog integration via CLI (list crawls, start crawl, export data)
- GSC API integration (OAuth, query data, impression-weighted anchor suggestions)
- Full page content matching (fetch + parse source pages)
- Grouped opportunity dashboard with sort/filter/export
- CSV export of results
- Graceful degradation when GSC is unavailable

### OUT of Scope (v1)
- Batch/multiple target URL processing (architected to support later)
- Google Sheets direct export (CSV export is sufficient for manual import)
- Custom Screaming Frog crawl configurations (uses default or existing config files)
- Content editing / CMS integration
- Non-descriptive anchor text audit (separate workflow)
- Crawl comparison / before-after analysis
- Scheduled/automated re-analysis

### v2 Candidates
- Batch URL processing
- Google Sheets API export
- Non-descriptive anchor text detection and replacement suggestions
- Crawl comparison mode
- Scheduled re-crawls

---

## 9. Security Considerations

- GSC OAuth tokens stored locally only (file-based token cache, not in a database)
- No user data leaves the local machine (all processing local)
- OAuth redirect uses `localhost` URI — no cloud callback endpoint needed
- SF CLI subprocess calls use argument escaping to prevent injection
- Page fetching respects `robots.txt` via configurable user-agent

---

## 10. Non-Goals

- This tool does NOT edit content or insert links — it identifies opportunities only
- This tool does NOT replace Screaming Frog — it consumes SF's output
- This tool is NOT a cloud service — it runs locally on the user's machine
- This tool does NOT require a database — state is ephemeral per analysis session
