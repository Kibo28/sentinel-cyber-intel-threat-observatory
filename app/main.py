"""Synology-friendly self-hosted threat intelligence observatory."""
import asyncio
import csv
import io
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import FileResponse, JSONResponse, Response
from . import store, ingest, notifications, preferences
from .sources import EXTERNAL

ROOT=Path(__file__).parent
TIMEZONE=os.environ.get("CTI_TIMEZONE","Europe/Zurich")
HOUR=int(os.environ.get("CTI_SYNC_HOUR","8"))
MINUTE=int(os.environ.get("CTI_SYNC_MINUTE","0"))
logger = logging.getLogger("uvicorn.error")

async def run_sync():
    try:
        await asyncio.to_thread(ingest.sync_all)
    except Exception:
        logger.exception("Unable to complete a feed refresh")

def queue_sync(app):
    task = app.state.sync_task
    if task is not None and not task.done():
        return False
    app.state.sync_task = asyncio.create_task(run_sync())
    return True


async def schedule_loop(app):
    completed = await asyncio.to_thread(store.last_completed_run)
    baseline = datetime.fromisoformat(completed) if completed else datetime.now(timezone.utc)
    last_run_day = None
    zone = ZoneInfo(TIMEZONE)
    while True:
        settings = await asyncio.to_thread(preferences.collection_settings)
        now = datetime.now(timezone.utc)
        if settings.interval_minutes is not None:
            finished = ingest.STATE["finished"]
            last = datetime.fromisoformat(finished) if finished else baseline
            if now >= last + timedelta(minutes=settings.interval_minutes):
                queue_sync(app)
        else:
            local = now.astimezone(zone)
            if (local.hour, local.minute) == (HOUR, MINUTE) and local.date() != last_run_day:
                queue_sync(app)
                last_run_day = local.date()
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app):
    store.init_db()
    app.state.sync_task = None
    task=asyncio.create_task(schedule_loop(app))
    if os.environ.get("CTI_RUN_ON_START","true").lower() in ("true","1","yes"):
        queue_sync(app)
    try:
        yield
    finally:
        task.cancel()
        tasks = [task]
        if app.state.sync_task is not None:
            app.state.sync_task.cancel()
            tasks.append(app.state.sync_task)
        await asyncio.gather(*tasks, return_exceptions=True)

app=FastAPI(title="Cyber Intel Threat Observatory",version="1.0.0",lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

@app.middleware("http")
async def security_headers(request,call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Cache-Control"]="no-store"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
    return response

def require_write_header(request:Request):
    if request.headers.get("X-CTI-Request")!="dashboard":
        raise HTTPException(403,"Missing same-origin write header")

@app.get("/health")
def health():return {"status":"ok"}

@app.get("/")
def index():return FileResponse(ROOT/"static"/"index.html",media_type="text/html")

@app.get("/static/{filename}")
def static(filename:str):
    if filename not in {"app.js","app.css"}:raise HTTPException(404)
    media="text/javascript" if filename.endswith("js") else "text/css"
    return FileResponse(ROOT/"static"/filename,media_type=media)

@app.get("/static/assets/{filename}")
def static_brand_asset(filename:str):
    # Explicit allowlist prevents arbitrary local-file disclosure.
    allowed={"cyber-intel-icon.png", "cyber-intel-wordmark.png"}
    if filename not in allowed:
        raise HTTPException(404)
    return FileResponse(ROOT/"static"/"assets"/filename,media_type="image/png")

@app.get("/api/stats")
def stats():
    s=store.stats();s["sync_running"]=ingest.STATE["running"];s["timezone"]=TIMEZONE;s["hour"]=HOUR;s["minute"]=MINUTE
    s["interval_minutes"] = preferences.collection_settings().interval_minutes
    return s

@app.get("/api/incidents")
def incidents(category:str="All",severity:str="All",q:str="",limit:int=500,offset:int=0):
    return {"items":store.list_items(category, q, severity, limit,offset=offset),"limit":min(limit,2000),"offset":offset}

@app.get("/api/incidents/{item_id}")
def incident_details(item_id:str):
    result=store.details(item_id)
    if not result:raise HTTPException(404,"Incident not found")
    return result

@app.get("/api/sources")
def sources():
    config = preferences.source_config()
    state={x["name"]:x for x in store.sources_status()}
    configured = []
    for source in config.feeds:
        status = state.get(source.name)
        if status and status["url"] != source.url:
            status = None
        configured.append({"name":source.name,"url":source.url,"type":source.source_type,
                           "category":source.category,"mode":"Feed","enabled":source.enabled,"status":status})
    configured.append({"name":"CISA KEV","url":ingest.CISA_KEV,"type":"official","category":"Vulnerabilities",
                       "mode":"JSON","enabled":config.kev_enabled,"status":state.get("CISA KEV")})
    external = [source.model_dump() for source in config.external]
    if config.epss_enabled:
        external.extend(source for source in EXTERNAL if source["name"] == "FIRST EPSS")
    return {"feeds":configured,"external":external,"config":config}

@app.put("/api/sources")
def update_sources(request:Request, config:preferences.SourceConfig):
    require_write_header(request)
    if not store.save_setting("sources", config.model_dump(exclude={"revision"}), config.revision):
        raise HTTPException(409, "Sources changed in another session. Reopen the editor to reload them.")
    return sources()

@app.get("/api/settings")
def collection_settings():
    return {**preferences.collection_settings().model_dump(), "email_available":notifications.email_available(),
            "timezone":TIMEZONE,"hour":HOUR,"minute":MINUTE}

@app.put("/api/settings")
def update_collection_settings(request:Request, settings:preferences.CollectionSettings):
    require_write_header(request)
    if settings.email_enabled and not notifications.email_available():
        raise HTTPException(422, "Configure SMTP on the NAS before enabling email alerts.")
    if not store.save_setting("collection", settings.model_dump(exclude={"revision"}), settings.revision):
        raise HTTPException(409, "Settings changed in another session. Reopen the editor to reload them.")
    return collection_settings()

@app.post("/api/sync")
async def sync(request:Request):
    require_write_header(request)
    if not queue_sync(request.app):return JSONResponse({"status":"already-running"},status_code=409)
    return JSONResponse({"status":"queued"},status_code=202)

@app.post("/api/import")
def import_items(request:Request,payload:dict=Body(...)):
    require_write_header(request)
    try: return store.import_legacy(payload)
    except ValueError as e:raise HTTPException(422,str(e))

@app.get("/api/export.json")
def export_json():
    with store.connect() as db:
        rows=[store.rowdict(x) for x in db.execute("SELECT * FROM incidents ORDER BY first_seen DESC").fetchall()]
    for row in rows:
        d=store.details(row["id"])
        row["sources"]=d["sources"]
        row["history"]=d["history"]
    return JSONResponse({"exported_at":store.utcnow(),"items":rows},headers={"Content-Disposition":"attachment; filename=cyber-intel-history.json"})

@app.get("/api/export.csv")
def export_csv():
    with store.connect() as db:
        rows=[store.rowdict(x) for x in db.execute("SELECT * FROM incidents ORDER BY first_seen DESC").fetchall()]
    if not rows:return Response("",media_type="text/csv")
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return Response("\ufeff"+output.getvalue(),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=cyber-intel-history.csv"})
