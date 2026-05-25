# Results UX Improvement Plan

**Date:** 2026-05-24
**Status:** ✅ Complete

---

- [x] **Task 1**: Fix Stat Labels
- [x] **Task 2**: Add Target Page Metadata + Keyword List to Dashboard
- [x] **Task 3**: Display Link Authority Help Tooltip
- [x] **Task 4**: Show SF Link Score Status
- [x] **Task 5**: Add "Copy Anchor" Button per Match
- [x] **Task 6**: Fix Scoring When GSC Is Unavailable

---

## Task 1: Fix Stat Labels ✅

**File:** `internal_linking_tool/static/index.html` (line 64-67)

**Change:**
```html
<!-- BEFORE -->
<div class="stat"><div class="sl">Pages</div><div class="sv" id="spg">0</div></div>
<div class="stat"><div class="sl">Opps</div><div class="sv" id="sop">0</div></div>

<!-- AFTER -->
<div class="stat"><div class="sl">Pages with Opps</div><div class="sv" id="spg">0</div></div>
<div class="stat"><div class="sl">Anchor Matches</div><div class="sv" id="sop">0</div></div>
```

**QA:** Stats cards show clearly labeled metrics.

---

## Task 2: Add Target Page Metadata + Keyword List to Dashboard ✅

**Files:** `analyzer.py` + `index.html`

**analyzer.py change** (line 148-159): Add `target_title`, `target_h1`, `keywords_list`, `gsc_connected` to meta dict:

```python
"meta": {
    ...
    "target_title": target_metadata.title,
    "target_h1": target_metadata.h1,
    "keywords_list": [kw["keyword"] for kw in build_impression_weighted_keywords(queries)][:20],
    "gsc_connected": self.gsc_client.is_authenticated if self.gsc_client else False,
}
```

**index.html change** (line 103-108): After stats grid, add a metadata summary section:

```html
<div id="target-info" style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:.5rem;padding:.75rem;margin-bottom:1rem;font-size:.8125rem;display:none">
  <strong>Target:</strong> <span id="ti-title"></span>
  <span style="color:#9ca3af;margin:0 .5rem">|</span>
  <strong>Keywords:</strong> <span id="ti-kw"></span>
  <span style="color:#9ca3af;margin:0 .5rem">|</span>
  <strong>GSC:</strong> <span id="ti-gsc"></span>
  <span style="color:#9ca3af;margin:0 .5rem">|</span>
  <strong>Method:</strong> <span id="ti-method"></span>
</div>
```

Populate in `lr()` function:
```javascript
var info = document.getElementById('target-info');
var hasLLM = (o[0]||{}).matches && o[0].matches.some(function(m){return m.generation_method==='llm'});
info.style.display = 'block';
document.getElementById('ti-title').textContent = (m.target_title || m.target_h1 || 'Unknown').substring(0,80);
document.getElementById('ti-kw').textContent = (m.keywords_list||[]).slice(0,8).join(', ') + ((m.keywords_list||[]).length > 8 ? ' ...' : '');
document.getElementById('ti-gsc').textContent = m.gsc_connected ? '✓ Connected' : '✗ Not connected';
document.getElementById('ti-method').textContent = hasLLM ? 'LLM (DeepSeek)' : 'Heuristic';
```

**QA:** Dashboard header shows target page title, keyword list, GSC status, and LLM/heuristic mode.

---

## Task 3: Display Link Authority Help Tooltip ✅

**File:** `index.html`

Add `title` attribute to Auth column header explaining what it means:
```html
<th style="width:70px;text-align:center" title="Link Authority: importance score from Screaming Frog (0-100). 0 = no score available.">Auth ⓘ</th>
```

**QA:** Hovering over "Auth ⓘ" shows explanation. Users understand why it's 0.

---

## Task 4: Show SF Link Score Status ✅

**File:** `analyzer.py` + `index.html`

Add `avg_link_authority` to meta to surface whether SF scores are available:
```python
"avg_link_authority": round(sum(p.link_authority for p in pages if p.is_eligible) / max(1, len([p for p in pages if p.is_eligible])), 1),
```

In dashboard, show warning if all scores are 0:
```javascript
if ((m.avg_link_authority||0) === 0) {
  document.getElementById('ti-gsc').insertAdjacentHTML('afterend', '<br><span style="color:#9a3412;font-size:.75rem">⚠ Link Authority is 0 for all pages — check Screaming Frog crawl settings</span>');
}
```

**QA:** Users see a warning when SF scores are missing, with guidance to fix.

---

## Task 5: Add "Copy Anchor" Button per Match ✅

**File:** `index.html` (line 118-123)

Add a copy button next to each anchor text so users can quickly copy the recommended anchor:

```javascript
return '<div style="margin-bottom:.25rem;display:flex;align-items:center;gap:.25rem">'+
  '<span class="chip '+(m.impression_share>=0.3?'cp':'cs')+'">'+(m.anchor_text||m.keyword)+' ('+Math.round((m.impression_share||0)*100)+'%)</span>'+
  gm+vars+
  '<button onclick="event.stopPropagation();navigator.clipboard.writeText(\''+(m.anchor_text||m.keyword).replace(/'/g,"\\'")+'\');this.textContent=\'✓\';setTimeout(function(){this.textContent=\'Copy\'}.bind(this),1000)" style="font-size:.625rem;padding:1px 4px;background:#e5e7eb;border:1px solid #d1d5db;border-radius:3px;cursor:pointer">Copy</button>'+
'</div>';
```

**QA:** Clicking "Copy" copies the anchor text to clipboard, button shows "✓" for 1 second.

---

## Task 6: Fix Scoring When GSC Is Unavailable ✅

**File:** `match_engine.py:34-35`

Current: `score_opportunity(link_authority, 0) = 0` — all pages tie at 0 when no GSC data.

Change to use link_authority alone when clicks=0:
```python
def score_opportunity(link_authority, organic_clicks):
    if organic_clicks == 0:
        return link_authority  # fallback: rank by authority alone
    return link_authority * math.log(organic_clicks + 1)
```

**QA:** When GSC is unavailable, pages are ranked by Link Authority instead of all tying at 0.

---

## Execution Order

```
Task 6 (match_engine scoring) ── independent
Task 2 (analyzer meta + HTML) ──┐
Task 1 (stat labels)          ──┤ all HTML changes
Task 3 (auth tooltip)         ──┤ can be combined
Task 4 (score warning)        ──┤ in one pass
Task 5 (copy button)          ──┘
```

---

## Acceptance Criteria — ALL MET ✅

1. ✅ Stat labels clearly describe what they measure
2. ✅ Target page title and keyword list visible in dashboard header
3. ✅ GSC connection status and generation method displayed
4. ✅ "Auth" column has tooltip explaining the score
5. ✅ Warning shown when all Link Authority scores are 0
6. ✅ "Copy" button on each anchor match copies to clipboard
7. ✅ Scoring works without GSC (authority-based ranking)
8. ✅ 65/65 tests still pass
