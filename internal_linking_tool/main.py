"""FastAPI application for the Internal Linking Tool."""

import uuid
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from internal_linking_tool.config import config
from internal_linking_tool.models import AnalysisRequest
from internal_linking_tool.sf_cli import SfCliManager, check_sf_installed
from internal_linking_tool.gsc_client import GscClient
from internal_linking_tool.analyzer import run_analysis
from internal_linking_tool.sse import sse_emitter

STATIC_DIR = Path(__file__).parent / "static"


def create_app():
    app = FastAPI(title="Internal Linking Tool", version="0.1.0")

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.state.analyses = {}
    app.state.sf_manager = SfCliManager()
    app.state.gsc_client = GscClient()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return index_path.read_text()
        return HTMLResponse("<h1>Internal Linking Tool</h1><p>Static files not found.</p>")

    @app.get("/api/health")
    async def health():
        sf_ok = check_sf_installed()
        gsc_ok = False
        try:
            gsc_ok = app.state.gsc_client.is_authenticated
        except Exception:
            pass
        return {"sf_installed": sf_ok, "sf_path": config.sf_cli_path, "gsc_configured": gsc_ok, "server": "ok"}

    @app.get("/api/crawls")
    async def get_crawls():
        try:
            crawls = app.state.sf_manager.list_crawls()
            return [{"id": c.id, "name": c.name, "date": c.date, "url_count": c.url_count} for c in crawls]
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/crawls")
    async def create_crawl(url: str = Query(...)):
        try:
            crawl_id = app.state.sf_manager.start_crawl(url)
            return {"crawl_id": crawl_id, "status": "running"}
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/crawls/{crawl_id}/status")
    async def get_crawl_status(crawl_id: str):
        try:
            status = app.state.sf_manager.crawl_status(crawl_id)
            return {"id": status.id, "phase": status.phase, "percent": status.percent, "urls_crawled": status.urls_crawled}
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/analyze")
    async def start_analysis(request: AnalysisRequest):
        analysis_id = str(uuid.uuid4())[:8]
        app.state.analyses[analysis_id] = {"status": "queued", "target_url": request.target_url}
        asyncio.create_task(_run_background_analysis(analysis_id, request, app))
        return {"analysis_id": analysis_id, "status": "queued"}

    @app.get("/api/analyze/{analysis_id}/stream")
    async def analysis_stream(analysis_id: str):
        if analysis_id not in app.state.analyses:
            raise HTTPException(status_code=404, detail="Analysis not found")
        sse_emitter.create_stream(analysis_id)

        async def event_generator():
            async for event in sse_emitter.stream(analysis_id):
                yield event
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/api/analyze/{analysis_id}/results")
    async def analysis_results(
        analysis_id: str,
        sort: str = "priority",
        min_authority: int = 0,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 100,
    ):
        data = app.state.analyses.get(analysis_id)
        if not data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        results = data.get("results", [])
        meta = data.get("meta", {})
        if min_authority > 0:
            results = [r for r in results if r.get("link_authority", 0) >= min_authority]
        if q:
            q_lower = q.lower()
            results = [r for r in results if q_lower in r.get("source_url", "").lower()
                       or any(q_lower in m.get("keyword", "").lower() for m in r.get("matches", []))]
        if sort == "clicks":
            results = sorted(results, key=lambda r: r.get("organic_clicks_90d", 0), reverse=True)
        elif sort == "matches":
            results = sorted(results, key=lambda r: r.get("match_count", 0), reverse=True)
        else:
            results = sorted(results,
                             key=lambda r: r.get("link_authority", 0) * (r.get("organic_clicks_90d", 0) or 1),
                             reverse=True)
        total = len(results)
        start = (page - 1) * per_page
        paged = results[start:start + per_page]
        return {"opportunities": paged, "meta": {**meta, "total": total, "page": page, "per_page": per_page}}

    @app.get("/api/analyze/{analysis_id}/export")
    async def export_results(analysis_id: str):
        import csv, io
        data = app.state.analyses.get(analysis_id)
        if not data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        results = data.get("results", [])
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Source URL", "Link Authority", "Clicks (90d)", "Match Count", "Best Anchor", "All Anchors"])
        for r in results:
            anchors = "; ".join(m.get("anchor_text", m.get("keyword", "")) for m in r.get("matches", []))
            writer.writerow([r["source_url"], r.get("link_authority", 0), r.get("organic_clicks_90d", 0),
                             r.get("match_count", 0), r.get("best_anchor", ""), anchors])
        output.seek(0)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": f"attachment; filename=opportunities-{analysis_id}.csv"})

    @app.get("/api/gsc/auth")
    async def gsc_auth():
        try:
            success = app.state.gsc_client.authenticate()
            return {"authenticated": success}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


async def _run_background_analysis(analysis_id, request, app):
    try:
        sf = app.state.sf_manager
        export = sf.export_crawl_data(request.crawl_id or "latest")
        result = await run_analysis(
            target_url=request.target_url,
            csv_path=export["internal_csv"],
            outlinks_csv=export.get("outlinks_csv"),
            stream_id=analysis_id,
        )
        app.state.analyses[analysis_id] = result
    except Exception as e:
        app.state.analyses[analysis_id] = {"error": str(e)}
        await sse_emitter.emit(analysis_id, "error", {"detail": str(e)})


app = create_app()


def main():
    import uvicorn
    uvicorn.run("internal_linking_tool.main:app", host=config.server_host, port=config.server_port, reload=True)


if __name__ == "__main__":
    main()
