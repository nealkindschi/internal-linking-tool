# Anchor Text Improvement — Implementation Plan

**Date:** 2026-05-24
**Status:** Approved — Ready for execution
**Architect:** Sisyphus
**Goal:** Transform raw GSC search queries into descriptive, natural anchor text that accurately describes the target page's content.

---

## Context

### Current Problem
`match_engine.py:88` and `anchor_engine.py:40` set `anchor_text = raw_gsc_query`. This produces terrible anchor text:
- "how to fix a PC fan" → question, not descriptive
- "best coffee machine 2024" → keyword-stuffed, includes year
- "green energy options" → sometimes ok, but no targeting context

### Best Practices (from 5 authoritative sources)
| Source | Key Rule |
|--------|----------|
| **Google** | Descriptive, concise, relevant to target page. NO "click here," "read more." Write naturally. |
| **Yoast** | Keyword-rich anchor text that clearly describes the destination page. Mix natural variations. |
| **Semrush** | Brief (≤5 words), not vague or clickbaity. Exact-match OK for internal links. |
| **Moz** | Descriptive keywords giving sense of target page topic. |
| **Siteimprove** | Descriptive, varied, keyword-aligned. |

### User Decisions (confirmed)
- **LLM**: DeepSeek V4 Pro (OpenAI-compatible API)
- **Target page fetch**: Yes — extract `<title>`, `<h1>`, slug, meta description
- **Variations**: Natural variation by source context, up to 3 per match
- **Fallback**: Optional LLM — heuristic fallback using page title/H1 when LLM unavailable
- **Scope**: Anchor generation ONLY — matching logic unchanged

---

## Architecture Changes

### Files Modified (6)
| File | Change |
|------|--------|
| `config.py` | Add LLM configuration (endpoint, api_key, model, enabled) |
| `models.py` | Add LLM config model, update Match fields |
| `page_fetcher.py` | Add `extract_page_metadata()` for title/H1/slug/description extraction |
| `anchor_engine.py` | Complete rewrite: LLM-based + heuristic fallback anchor generation |
| `match_engine.py` | Remove `anchor_text = kw_text` line (let anchor_engine handle it) |
| `analyzer.py` | Add target page fetch step, pass target metadata to anchor engine |

### Files Created (1)
| File | Purpose |
|------|---------|
| `llm_client.py` | OpenAI-compatible LLM client for DeepSeek V4 Pro |

### Tests Updated (1)
| File | Change |
|------|--------|
| `tests/test_anchor_engine.py` | Update for new logic, add LLM mock tests, heuristic fallback tests |

---

## Task 1: LLM Client (`llm_client.py` — NEW)

### Objective
Create an OpenAI-compatible client for DeepSeek V4 Pro that generates anchor text from target page context + GSC keywords + source sentence context.

### Design
```python
class LlmAnchorClient:
    def __init__(self, endpoint, api_key, model="deepseek-chat"):
        # Uses OpenAI client pointed at DeepSeek endpoint
        self.client = OpenAI(base_url=endpoint, api_key=api_key)
        self.model = model

    def generate_anchors(self, target_context, keyword, source_context, max_variations=3):
        # Calls LLM with structured prompt
        # Returns list of 1-3 anchor text strings

    def is_available(self):
        # Check if client is configured and reachable
```

### Prompt Design
```
You are an internal linking specialist for SEO.

TARGET PAGE:
  Title: "{title}"
  Heading: "{h1}"
  Topic: "{slug_words}"

SOURCE PAGE CONTEXT:
  A page mentions "{keyword}" in this sentence: "{context_sentence}"

Generate {max_variations} natural, descriptive anchor text variations for a link pointing to the target page.

RULES (CRITICAL):
- Must accurately describe what the reader will find on the target page
- 2-5 words per anchor
- NOT generic: NO "click here," "read more," "learn more," "this article"
- Write naturally, not keyword-stuffed
- When possible, incorporate the keyword naturally
- Each variation should be distinct from the others
- Anchor text should feel like natural prose in the source sentence context

Return ONLY valid JSON: {{"anchors": ["anchor1", "anchor2"]}}
```

### Error Handling
- Connection errors → return None (trigger heuristic fallback)
- Invalid JSON response → retry once, then fallback
- Rate limiting → wait and retry once
- Empty response → fallback

### Configuration
- Endpoint: `https://api.deepseek.com/v1` (configurable)
- API key: from `DEEPSEEK_API_KEY` env var
- Model: `deepseek-chat` (configurable)
- Token limit: 256 output tokens

### QA
- [ ] Unit test: mock OpenAI client, verify prompt construction
- [ ] Unit test: handles JSON parse errors gracefully
- [ ] Unit test: returns None on connection failure

---

## Task 2: Page Metadata Extraction (`page_fetcher.py` — MODIFY)

### Objective
Extract structured metadata from target page HTML for use in anchor generation.

### New Function
```python
@dataclass
class PageMetadata:
    title: str = ""
    h1: str = ""
    slug: str = ""
    description: str = ""

def extract_page_metadata(html, url):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title else ""
    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""
    slug = _slug_to_words(url)
    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""
    return PageMetadata(title=title, h1=h1, slug=slug, description=description)

def _slug_to_words(url):
    from urllib.parse import urlparse
    path = urlparse(url).path.strip("/")
    if not path:
        return ""
    last_segment = path.split("/")[-1]
    return last_segment.replace("-", " ").replace("_", " ")
```

### Integration
- Called by `analyzer.py` after fetching target page
- Metadata passed to `AnchorEngine` for LLM prompt and heuristic fallback

### QA
- [ ] Unit test: extracts title, h1, slug from valid HTML
- [ ] Unit test: handles missing elements (no title, no h1)
- [ ] Unit test: handles complex URLs (/blog/2024/how-to-fix-pc-fan)

---

## Task 3: Config Update (`config.py` — MODIFY)

### New Fields
```python
# LLM
llm_enabled: bool = True  # Set False to force heuristic-only
llm_endpoint: str = "https://api.deepseek.com/v1"
llm_model: str = "deepseek-chat"
llm_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
llm_max_variations: int = 3
```

### QA
- [ ] Verify config loads from env vars
- [ ] Verify `llm_enabled=False` disables LLM path

---

## Task 4: Models Update (`models.py` — MODIFY)

### Changes
- Add `variations` field to `Match` model (list of alternative anchor texts)
- Add `generation_method` field to `Match` ("llm" or "heuristic")
- Remove `impression_share` from being the only signal

```python
class Match(BaseModel):
    keyword: str
    anchor_text: str           # Primary recommended anchor
    variations: list[str] = []  # Alternative anchors (up to 3 total including primary)
    generation_method: str = "heuristic"  # "llm" or "heuristic"
    impression_share: float
    context: str
```

### QA
- [ ] Pydantic model validates with both "llm" and "heuristic" methods
- [ ] variations field accepts empty list

---

## Task 5: Anchor Engine Rewrite (`anchor_engine.py` — REWRITE)

### Objective
Replace simple keyword-copy logic with LLM-powered + heuristic fallback anchor generation.

### New Class Design
```python
class AnchorEngine:
    def __init__(self, llm_client=None, max_variations=3):
        self.llm_client = llm_client
        self.max_variations = max_variations

    def generate_anchors(self, target_metadata, keyword, source_context):
        """
        Returns (primary_anchor, variations_list, method)
        Tries LLM first, falls back to heuristic.
        """
        if self.llm_client and self.llm_client.is_available():
            anchors = self._generate_via_llm(target_metadata, keyword, source_context)
            if anchors:
                return (anchors[0], anchors[1:], "llm")
        return self._generate_via_heuristic(target_metadata, keyword, source_context)

    def _generate_via_llm(self, target_metadata, keyword, source_context):
        """Call LLM, return list of anchors or None on failure."""
        ...

    def _generate_via_heuristic(self, target_metadata, keyword, source_context):
        """
        Heuristic anchor generation:
        - Primary: target page title (trimmed to first 6 words)
        - Secondary: H1 text
        - Tertiary: keyword itself (but cleaned - lowercase, trimmed)
        - Returns (primary, [secondary, tertiary])
        """
        ...

    def _clean_keyword(self, keyword):
        """Remove year suffixes, question words from keyword for fallback."""
        ...

    def enrich_opportunities(self, opportunities, queries, target_metadata):
        """
        For each match in each opportunity:
        1. Generate anchors using target_metadata + keyword + source context
        2. Set anchor_text, variations, generation_method
        3. Preserve impression_share from GSC
        """
        ...

    def build_anchor_list(self, queries):
        """Kept for backward compatibility — returns impression-weighted keywords."""
        return build_impression_weighted_keywords(queries)
```

### Heuristic Rules
```
Primary anchor priority:
  1. Target page title (first 6 words max, stripped of site name separators)
  2. Target page H1
  3. URL slug as spaced words
  4. Cleaned GSC keyword as last resort

Keyword cleaning:
  - Remove trailing year: "best laptops 2024" → "best laptops"
  - Strip question words: "how to fix pc fan" → "fix pc fan"
  - Lowercase, strip extra whitespace
```

### Legacy Support
- Keep `get_variations()` and `distribute_anchors()` for backward compatibility
- Mark as deprecated with docstring

### QA
- [ ] Unit test: LLM path mocked, generates anchors correctly
- [ ] Unit test: Heuristic fallback uses title → H1 → slug → keyword cascade
- [ ] Unit test: Empty target_metadata handled gracefully
- [ ] Unit test: _clean_keyword removes year and question words
- [ ] Unit test: enrich_opportunities sets all match fields correctly

---

## Task 6: Match Engine Update (`match_engine.py` — MODIFY)

### Change
Line 88: Remove `"anchor_text": kw_text` assignment. Anchor text is now generated by `AnchorEngine`.

```python
# BEFORE (line 84-91):
matches.append({
    "source_url": page.url,
    "link_authority": page.link_authority,
    "organic_clicks_90d": page.gsc_clicks,
    "keyword": kw_text,
    "anchor_text": kw_text,           # ← REMOVE THIS LINE
    "impression_share": kw.get("impression_share", 0),
    "context": context,
})

# AFTER:
matches.append({
    "source_url": page.url,
    "link_authority": page.link_authority,
    "organic_clicks_90d": page.gsc_clicks,
    "keyword": kw_text,
    # anchor_text set later by AnchorEngine
    "impression_share": kw.get("impression_share", 0),
    "context": context,
})
```

### QA
- [ ] Verify matches dict produced by `find_opportunities()` no longer has `anchor_text` key
- [ ] Verify existing tests still pass (they'll need anchor_text removed from assertions)

---

## Task 7: Analyzer Update (`analyzer.py` — MODIFY)

### Changes
1. **Add target page fetch step** before anchor enrichment
2. **Pass target metadata to AnchorEngine**
3. **Initialize LLM client conditionally**

```python
class Analyzer:
    def __init__(self, target_url, gsc_client=None, page_fetcher=None):
        ...
        self.anchor_engine = AnchorEngine(
            llm_client=self._init_llm_client(),
            max_variations=3
        )

    def _init_llm_client(self):
        """Initialize LLM client from config. Returns None if disabled."""
        if not config.llm_enabled or not config.llm_api_key:
            return None
        return LlmAnchorClient(...)

    async def _fetch_target_metadata(self):
        """Fetch target page and extract metadata."""
        fetched = await self.page_fetcher.fetch(self.target_url)
        if fetched.success:
            return extract_page_metadata(fetched.html_raw, self.target_url)
        return PageMetadata()

    async def run(self, csv_path, outlinks_csv=None, stream_id=None):
        ...
        # NEW: Fetch target page metadata after GSC fetch
        state.set_phase("target_fetch", "Analyzing target page...", 20)
        target_metadata = await self._fetch_target_metadata()

        ...
        # MODIFIED: Pass target_metadata to enrichment
        enriched = self.enrich(opportunities, queries, target_metadata)
        ...

    def enrich(self, opportunities, queries, target_metadata):
        return self.anchor_engine.enrich_opportunities(
            opportunities, queries, target_metadata
        )
```

### Phase Updates
```
Old pipeline: GSC fetch → CSV parse → Page scan → Matching → Anchor enrichment
New pipeline: GSC fetch → Target page fetch → CSV parse → Page scan → Matching → Anchor enrichment
```

### QA
- [ ] Integration test: full pipeline runs with target metadata
- [ ] Integration test: gracefully handles target page fetch failure (empty metadata)
- [ ] Integration test: LLM disabled → heuristic anchors produced

---

## Task 8: Test Updates (`tests/test_anchor_engine.py` — MODIFY)

### New Tests
| Test | What it verifies |
|------|-----------------|
| `test_llm_generates_anchors` | Mock LLM client, verify anchors returned |
| `test_heuristic_fallback_on_llm_failure` | LLM unavailable → heuristic kicks in |
| `test_heuristic_uses_title_first` | Title exists → used as primary anchor |
| `test_heuristic_falls_to_h1` | No title → H1 used |
| `test_heuristic_falls_to_slug` | No title, no H1 → slug used |
| `test_heuristic_falls_to_keyword` | Nothing else → cleaned keyword used |
| `test_clean_keyword_removes_year` | "best laptops 2024" → "best laptops" |
| `test_clean_keyword_strips_questions` | "how to fix pc fan" → "fix pc fan" |
| `test_enrich_sets_variations` | enrich_opportunities sets variations field |
| `test_enrich_sets_generation_method` | Sets "llm" or "heuristic" correctly |
| `test_backward_compat_no_anchor_in_matches` | Match engine output no longer has anchor_text |

### Updated Existing Tests
- Remove assertions checking `anchor_text == keyword` in old tests
- Update `enrich_opportunities` tests to pass `target_metadata`

### QA
- [ ] All new tests pass
- [ ] All existing tests pass (updated for new behavior)
- [ ] Running `python -m pytest tests/ -v` shows full suite green

---

## Task 9: Frontend Update (`static/app.js` — MODIFY if needed)

### Changes
If the dashboard renders anchor text variations, update to show:
- Primary anchor text prominently
- Variations listed below
- Generation method badge (optional: "LLM" vs "Heuristic" indicator)

### QA
- [ ] Dashboard renders anchor text correctly
- [ ] Variations visible in row expansion

---

## Task 10: Documentation (`README.md` — MODIFY)

### Changes
- Add LLM configuration section
- Document `DEEPSEEK_API_KEY` env var
- Explain heuristic fallback behavior

---

## Execution Order & Dependencies

```
Task 1 (llm_client.py)     ──┐
Task 2 (page_fetcher.py)   ──┤
Task 3 (config.py)         ──┼──► Task 5 (anchor_engine.py) ──► Task 7 (analyzer.py)
Task 4 (models.py)         ──┘                                        │
Task 6 (match_engine.py)   ──────────────────────────────────────────┘
                                                                      │
                                                              Task 8 (tests)
                                                              Task 9 (frontend)
                                                              Task 10 (docs)
```

**Wave 1 (parallel):** Tasks 1, 2, 3, 4, 6 — all independent
**Wave 2:** Task 5 — depends on Tasks 1-4
**Wave 3:** Task 7 — depends on Tasks 2, 5, 6
**Wave 4 (parallel):** Tasks 8, 9, 10 — depend on all above

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM API costs per analysis | Medium | Cache LLM results per (target_url + keyword) pair. Configurable max tokens. |
| Target page not accessible | Low | Graceful fallback to heuristic with empty metadata. |
| DeepSeek API changes | Low | OpenAI-compatible API is stable. Configurable endpoint. |
| Heuristic produces generic anchors | Medium | Test against diverse page titles. Fallback cascade ensures something is always returned. |
| Breaking existing GSC-only pipeline | Low | GSC integration unchanged. Anchor enrichment is additive. |

---

## Acceptance Criteria

1. **Anchor text is descriptive**: Generated anchors describe the target page's content (not raw GSC queries)
2. **LLM works when configured**: With valid API key, anchors are LLM-generated
3. **Heuristic works as fallback**: Without LLM, anchors use target page metadata
4. **Up to 3 variations per match**: Each match has primary + up to 2 alternatives
5. **`generation_method` tracked**: Each match knows if it was LLM or heuristic
6. **Backward compatible**: GSC-only pipeline (no target page fetch) still works
7. **All tests pass**: `python -m pytest tests/ -v` exits 0
8. **Dashboard renders correctly**: Frontend shows new anchor fields
