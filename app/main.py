"""Synology-friendly self-hosted threat intelligence observatory."""
import asyncio
import csv
import hmac
import io
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Request, Depends, Body
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from . import store, ingest
from .sources import FEEDS, EXTERNAL

ROOT=Path(__file__).parent
USERNAME=os.environ.get("CTI_USERNAME", "")
PASSWORD=os.environ.get("CTI_PASSWORD", "")
if not USERNAME or not PASSWORD or len(PASSWORD)<20 or "REPLACE_WITH" in PASSWORD:
    raise RuntimeError("Set a unique CTI_PASSWORD (20+ characters) and CTI_USERNAME in .env")
TIMEZONE=os.environ.get("CTI_TIMEZONE","Europe/Zurich")
HOUR=int(os.environ.get("CTI_SYNC_HOUR","8"))
MINUTE=int(os.environ.get("CTI_SYNC_MINUTE","0"))
security=HTTPBasic(auto_error=False)

async def run_sync():
    await asyncio.to_thread(ingest.sync_all)

async def daily_loop():
    """Daily schedule in Europe/Zurich with DST handling and no external scheduler."""
    last_run_day=None
    while True:
        now=datetime.now(ZoneInfo(TIMEZONE))
        date_key=now.date().isoformat()
        if now.hour==HOUR and now.minute>=MINUTE and now.minute<=MINUTE+1 and last_run_day!=date_key:
            last_run_day=date_key
            await run_sync()
        await asyncio.sleep(35)

@asynccontextmanager
async def lifespan(app):
    store.init_db()
    task=asyncio.create_task(daily_loop())
    initial=None
    if os.environ.get("CTI_RUN_ON_START","true").lower() in ("true","1","yes"):
        initial=asyncio.create_task(run_sync())
    yield
    task.cancel()
    if initial and not initial.done():initial.cancel()
    try:await task
    except asyncio.CancelledError:pass

app=FastAPI(title="Cyber Intel Threat Observatory",version="1.0.0",lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

def auth(credentials:HTTPBasicCredentials | None=Depends(security)):
    if credentials is None or not (hmac.compare_digest(credentials.username.encode(),USERNAME.encode()) and hmac.compare_digest(credentials.password.encode(),PASSWORD.encode())):
        raise HTTPException(401,detail="Authentication required",headers={'WWW-Authenticate':'Basic realm="Cyber Intel Threat Observatory", charset="UTF-8"'})
    return True

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
def index(_=Depends(auth)):return FileResponse(ROOT/"static"/"index.html",media_type="text/html")

@app.get("/static/{filename}")
def static(filename:str,_=Depends(auth)):
    if filename not in {"app.js","app.css"}:raise HTTPException(404)
    media="text/javascript" if filename.endswith("js") else "text/css"
    return FileResponse(ROOT/"static"/filename,media_type=media)

@app.get("/static/assets/{filename}")
def static_brand_asset(filename:str,_=Depends(auth)):
    # Explicit allowlist prevents arbitrary local-file disclosure.
    allowed={"cyber-intel-icon.png", "cyber-intel-wordmark.png"}
    if filename not in allowed:
        raise HTTPException(404)
    return FileResponse(ROOT/"static"/"assets"/filename,media_type="image/png")

@app.get("/api/stats")
def stats(_=Depends(auth)):
    s=store.stats();s["sync_running"]=ingest.STATE["running"];s["timezone"]=TIMEZONE;s["hour"]=HOUR;s["minute"]=MINUTE
    return s

@app.get("/api/incidents")
def incidents(category:str="All",severity:str="All",q:str="",limit:int=500,offset:int=0,_=Depends(auth)):
    return {"items":store.list_items(category, q, severity, limit,offset=offset),"limit":min(limit,2000),"offset":offset}

@app.get("/api/incidents/{item_id}")
def incident_details(item_id:str,_=Depends(auth)):
    result=store.details(item_id)
    if not result:raise HTTPException(404,"Incident not found")
    return result

@app.get("/api/sources")
def sources(_=Depends(auth)):
    state={x["name"]:x for x in store.sources_status()}
    configured=[{"name":s.name,"url":s.url,"type":s.source_type,"category":s.category,"mode":"Feed","status":state.get(s.name)} for s in FEEDS]
    configured.append({"name":"CISA KEV","url":ingest.CISA_KEV,"type":"official","category":"Vulnerabilities","mode":"JSON","status":state.get("CISA KEV")})
    return {"feeds":configured,"external":EXTERNAL}

@app.post("/api/sync")
async def sync(request:Request,_=Depends(auth)):
    require_write_header(request)
    if ingest.STATE["running"]:return JSONResponse({"status":"already-running"},status_code=409)
    asyncio.create_task(run_sync())
    return JSONResponse({"status":"queued"},status_code=202)

@app.post("/api/import")
def import_items(request:Request,payload:dict=Body(...),_=Depends(auth)):
    require_write_header(request)
    try: return store.import_legacy(payload)
    except ValueError as e:raise HTTPException(422,str(e))

@app.get("/api/export.json")
def export_json(_=Depends(auth)):
    with store.connect() as db:
        rows=[store.rowdict(x) for x in db.execute("SELECT * FROM incidents ORDER BY first_seen DESC").fetchall()]
    for row in rows:
        d=store.details(row["id"])
        row["sources"]=d["sources"]
        row["history"]=d["history"]
    return JSONResponse({"exported_at":store.utcnow(),"items":rows},headers={"Content-Disposition":"attachment; filename=cyber-intel-history.json"})

@app.get("/api/export.csv")
def export_csv(_=Depends(auth)):
    with store.connect() as db:
        rows=[store.rowdict(x) for x in db.execute("SELECT * FROM incidents ORDER BY first_seen DESC").fetchall()]
    if not rows:return Response("",media_type="text/csv")
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return Response("\ufeff"+output.getvalue(),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=cyber-intel-history.csv"})
