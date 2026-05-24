window.app = function() {
  return {
    step: 'input',
    targetUrl: '',
    analysisId: null,
    loading: false,
    loadingCrawls: false,
    errorMessage: '',
    progress: { percent: 0, detail: '' },
    opportunities: [],
    meta: {},
    crawls: [],
    selectedCrawlId: null,
    gscConnected: false,
    filterQuery: '',
    minAuthority: '0',
    sortBy: 'priority',
    eventSource: null,

    init() { this.checkGscStatus(); },

    async checkGscStatus() {
      try { const r = await fetch('/api/health'); const d = await r.json(); this.gscConnected = d.gsc_configured; } catch {}
    },

    async connectGsc() {
      try { const r = await fetch('/api/gsc/auth'); const d = await r.json(); this.gscConnected = d.authenticated; }
      catch (err) { this.errorMessage = 'GSC auth failed. Check credentials file.'; this.step = 'error'; }
    },

    async goToCrawlSelect() {
      if (!this.targetUrl) return;
      this.step = 'crawl_select'; this.loadingCrawls = true; this.crawls = []; this.selectedCrawlId = null;
      try {
        const r = await fetch('/api/crawls').then(async r => { if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'SF error'); } return r.json(); });
        this.crawls = await r.json();
        if (this.crawls.length === 1) this.selectedCrawlId = this.crawls[0].id;
      } catch (err) {
        if ((err.message || '').toLowerCase().includes('gui') || (err.message || '').toLowerCase().includes('headless'))
          this.errorMessage = 'Screaming Frog GUI is open. Close Screaming Frog before using this tool.';
        else
          this.errorMessage = 'Could not load crawls. Is Screaming Frog installed?';
        this.step = 'error';
      }
      this.loadingCrawls = false;
    },

    startNewCrawl() {
      this.step = 'progress';
      this.progress = { percent: 5, detail: 'Starting new crawl...' };
      fetch('/api/crawls?url=' + encodeURIComponent(this.targetUrl), { method: 'POST' }).then(async r => { if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'SF error'); } return r.json(); })
        .then(r => r.json())
        .then(data => { this.selectedCrawlId = data.crawl_id; this.startAnalysis(); })
        .catch(err => {
          if ((err.message || '').toLowerCase().includes('gui') || (err.message || '').toLowerCase().includes('headless'))
            this.errorMessage = 'Screaming Frog GUI is open. Close Screaming Frog before using this tool.';
          else
            this.errorMessage = 'Failed to start crawl: ' + (err.message || 'unknown error');
          this.step = 'error';
        });
    },

    async startAnalysis() {
      this.loading = true; this.step = 'progress'; this.errorMessage = '';
      const body = { target_url: this.targetUrl };
      if (this.selectedCrawlId) body.crawl_id = this.selectedCrawlId;
      try {
        const r = await fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const d = await r.json(); this.analysisId = d.analysis_id;
        this.eventSource = new EventSource('/api/analyze/' + this.analysisId + '/stream');
        this.eventSource.addEventListener('progress', (e) => { const p = JSON.parse(e.data); this.progress = p; if (p.phase === 'complete') this.loadResults(); });
        this.eventSource.addEventListener('error', (e) => { const err = JSON.parse(e.data); this.errorMessage = err.detail || 'Analysis failed'; this.step = 'error'; this.loading = false; this.eventSource.close(); });
        this.eventSource.onerror = () => { setTimeout(() => this.loadResults(), 2000); };
      } catch (err) { this.errorMessage = err.message || 'Failed'; this.step = 'error'; this.loading = false; }
    },

    async loadResults() {
      try {
        const r = await fetch('/api/analyze/' + this.analysisId + '/results');
        const d = await r.json();
        this.opportunities = (d.opportunities || []).map(o => ({ ...o, _expanded: false }));
        this.meta = d.meta || {}; this.step = 'results'; this.loading = false;
        if (this.eventSource) this.eventSource.close();
      } catch (err) {
        setTimeout(async () => {
          try {
            const r = await fetch('/api/analyze/' + this.analysisId + '/results');
            const d = await r.json();
            this.opportunities = (d.opportunities || []).map(o => ({ ...o, _expanded: false }));
            this.meta = d.meta || {}; this.step = 'results'; this.loading = false;
            if (this.eventSource) this.eventSource.close();
          } catch { this.errorMessage = 'Failed to load results'; this.step = 'error'; this.loading = false; }
        }, 2000);
      }
    },

    cancelAnalysis() { if (this.eventSource) this.eventSource.close(); this.step = 'input'; this.loading = false; },

    resetAll() {
      if (this.eventSource) this.eventSource.close();
      this.step = 'input'; this.targetUrl = ''; this.analysisId = null;
      this.opportunities = []; this.meta = {}; this.crawls = [];
      this.selectedCrawlId = null; this.loading = false; this.errorMessage = '';
    },

    filteredOpportunities() {
      let opps = [...this.opportunities];
      if (this.minAuthority > 0) opps = opps.filter(o => o.link_authority >= parseInt(this.minAuthority));
      if (this.filterQuery) {
        const q = this.filterQuery.toLowerCase();
        opps = opps.filter(o => o.source_url.toLowerCase().includes(q) || (o.matches || []).some(m => (m.keyword || '').toLowerCase().includes(q)));
      }
      if (this.sortBy === 'clicks') opps.sort((a, b) => (b.organic_clicks_90d || 0) - (a.organic_clicks_90d || 0));
      else if (this.sortBy === 'matches') opps.sort((a, b) => (b.match_count || 0) - (a.match_count || 0));
      else opps.sort((a, b) => { const sa = (a.link_authority || 0) * ((a.organic_clicks_90d || 0) + 1); const sb = (b.link_authority || 0) * ((b.organic_clicks_90d || 0) + 1); return sb - sa; });
      return opps;
    },

    exportCSV() { if (this.analysisId) window.open('/api/analyze/' + this.analysisId + '/export', '_blank'); }
  };
};
