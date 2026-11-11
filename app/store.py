"""Durable SQLite storage with deterministic incident and article deduplication."""
import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

DB_PATH = os.environ.get("CTI_DB_PATH", "/data/cti.db")
CVEPAT = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.I)
STOPWORDS = {"the","a","an","and","or","for","to","in","of","on","with","as","at","from","after","is","new","update","reported","report","reportedly","cyber","attack","attacks","flaw","vulnerability","vulnerabilities","critical","high","security","has","its","via","over","against","la","le","les","de","des","dans","une","un","aux","du","sur","par","en"}

def utcnow(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def clean(s, n=4000): return str(s or "").strip()[:n]
def canonical_url(u):
    try:
        p=urlsplit(u.strip());
        if p.scheme not in ("http", "https") or not p.netloc: return ""
        qs=urlencode([(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not (k.lower().startswith("utm_") or k.lower() in ("fbclid","gclid","mc_cid","mc_eid"))])
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/",qs,""))
    except Exception: return ""

def fingerprint(title):
    tokens=re.findall(r"[a-z0-9]+",str(title).lower())
    return " ".join(x for x in tokens if x not in STOPWORDS)

def calc_id(item):
    explicit=str(item.get("cve", "")).upper()
    if item.get("category")=="Vulnerabilities" and CVEPAT.fullmatch(explicit): return explicit
    cves=sorted(set(CVEPAT.findall(" ".join([item.get("title", ""),item.get("summary", "")]))))
    if len(cves)==1 and item.get("category")=="Vulnerabilities": return cves[0].upper()
    link=canonical_url(item.get("url", ""))
    if link: return "URL-"+hashlib.sha256(link.encode()).hexdigest()[:18]
    return "TTL-"+hashlib.sha256((item.get("title", "")+item.get("published_at", "")).encode()).hexdigest()[:18]

@contextmanager
def connect():
    os.makedirs(os.path.dirname(DB_PATH) or '.',exist_ok=True)
    db=sqlite3.connect(DB_PATH,timeout=30)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    finally: db.close()

def init_db():
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS incidents (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '',
          category TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'Info',
          primary_url TEXT NOT NULL DEFAULT '', source_name TEXT NOT NULL DEFAULT '',
          source_type TEXT NOT NULL DEFAULT 'news', confidence TEXT NOT NULL DEFAULT 'Reported / unverified',
          region TEXT NOT NULL DEFAULT 'Global', vendor TEXT NOT NULL DEFAULT '', product TEXT NOT NULL DEFAULT '',
          cve TEXT NOT NULL DEFAULT '', cvss TEXT NOT NULL DEFAULT '', affected_versions TEXT NOT NULL DEFAULT '',
          remediation TEXT NOT NULL DEFAULT '', exploited INTEGER NOT NULL DEFAULT 0,
          epss_score REAL,
          event_date TEXT NOT NULL DEFAULT '', published_at TEXT NOT NULL DEFAULT '',
          first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, last_changed TEXT NOT NULL,
          fingerprint TEXT NOT NULL DEFAULT '', archived INTEGER NOT NULL DEFAULT 0,
          updates INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS incident_sources (
          incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
          url TEXT NOT NULL, name TEXT NOT NULL, first_seen TEXT NOT NULL,
          PRIMARY KEY(incident_id,url)
        );
        CREATE TABLE IF NOT EXISTS incident_organization (
          incident_id TEXT PRIMARY KEY REFERENCES incidents(id) ON DELETE CASCADE,
          favorite INTEGER NOT NULL DEFAULT 0,
          tags TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS source_url_idx ON incident_sources(url);
        CREATE TABLE IF NOT EXISTS incident_changes (
          id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
          change_at TEXT NOT NULL, description TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS incident_changes_incident_idx ON incident_changes(incident_id, id);
        CREATE TABLE IF NOT EXISTS feed_status (
          name TEXT PRIMARY KEY, url TEXT NOT NULL, last_checked TEXT NOT NULL,
          status TEXT NOT NULL, fetched INTEGER NOT NULL DEFAULT 0, details TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS sync_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, started TEXT NOT NULL, completed TEXT,
          new_items INTEGER NOT NULL DEFAULT 0, updates INTEGER NOT NULL DEFAULT 0,
          duplicates INTEGER NOT NULL DEFAULT 0, error_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY, value TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1
        );
        """)

def get_setting(key):
    with connect() as db:
        row = db.execute("SELECT value, revision FROM settings WHERE key=?", (key,)).fetchone()
    return (json.loads(row["value"]), row["revision"]) if row else (None, 0)

def save_setting(key, value, revision):
    with connect() as db:
        data = json.dumps(value)
        if revision == 0:
            result = db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (key, data))
        else:
            result = db.execute(
                "UPDATE settings SET value=?,revision=revision+1 WHERE key=? AND revision=?",
                (data, key, revision),
            )
        return result.rowcount == 1

def last_completed_run():
    with connect() as db:
        return db.execute("SELECT MAX(completed) FROM sync_runs").fetchone()[0]

def rowdict(row): return dict(row) if row else None

def match_existing(db,item):
    lid=calc_id(item)
    exact=db.execute("SELECT id FROM incidents WHERE id=?",(lid,)).fetchone()
    if exact: return exact["id"]
    link=canonical_url(item.get("url", ""))
    if link and item.get("source_name")!="CISA KEV":
        found=db.execute("SELECT incident_id FROM incident_sources WHERE url=?",(link,)).fetchone()
        if found: return found["incident_id"]
    cves=list(set(CVEPAT.findall(item.get("title", "")+" "+item.get("summary",""))))
    if len(cves)==1 and item["category"]=="Vulnerabilities":
        found=db.execute("SELECT id FROM incidents WHERE cve=? AND category='Vulnerabilities' LIMIT 1",(cves[0].upper(),)).fetchone()
        if found: return found["id"]
    fp=fingerprint(item.get("title", ""))
    if len(fp)<14: return None
    candidates=db.execute("SELECT id, fingerprint, first_seen, cve FROM incidents WHERE category=? ORDER BY first_seen DESC LIMIT 450",(item["category"],)).fetchall()
    for row in candidates:
        other=row["fingerprint"]
        if cves and row["cve"] and row["cve"].upper() not in [v.upper() for v in cves]: continue
        if not other: continue
        x=set(fp.split());y=set(other.split())
        if len(x)<3 or len(y)<3:continue
        jaccard=len(x&y)/len(x|y)
        if fp==other or (jaccard>=.83 and SequenceMatcher(None,fp,other).ratio()>=.85): return row["id"]
    return None

def upsert(item, official_update=False):
    """Return 'new', 'updated' (only verified material CISA change), or 'duplicate'."""
    now=utcnow()
    link=canonical_url(item.get("url", ""))
    item={**item,"url":link,"title":clean(item.get("title"),350),"summary":clean(item.get("summary"),2200)}
    item.setdefault("category","Cyberattacks")
    item.setdefault("severity","Info")
    with connect() as db:
        old_id=match_existing(db,item)
        if old_id:
            old=db.execute("SELECT * FROM incidents WHERE id=?",(old_id,)).fetchone()
            if link:
                db.execute("INSERT OR IGNORE INTO incident_sources(incident_id,url,name,first_seen) VALUES (?,?,?,?)",(old_id,link,clean(item.get('source_name',''),100),now))
            important=(official_update and old["exploited"]==0 and item.get("exploited") and item.get("source_type")=="official")
            if important:
                msg="Official CISA KEV listing confirms known exploitation"
                db.execute("UPDATE incidents SET last_seen=?,last_changed=?,exploited=1,severity='High',remediation=CASE WHEN ?<>'' THEN ? ELSE remediation END,updates=updates+1 WHERE id=?",(now,now,item.get("remediation", ""),item.get("remediation", ""),old_id))
                db.execute("INSERT INTO incident_changes(incident_id,change_at,description,source_url) VALUES(?,?,?,?)",(old_id,now,msg,link))
                return "updated"
            db.execute("UPDATE incidents SET last_seen=? WHERE id=?",(now,old_id))
            return "duplicate"
        cves=list(set(CVEPAT.findall(item["title"]+" "+item["summary"])))
        cve=cves[0].upper() if len(cves)==1 else clean(item.get("cve",""),100)
        iid=calc_id(item)
        first_seen=now
        if item.get("source_type")=="import":
            dated=str(item.get("import_first_seen", ""))
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}",dated):first_seen=dated+"T12:00:00+00:00"
        vals=(iid,item["title"],item["summary"],item["category"],item["severity"],link,clean(item.get("source_name"),100),item.get("source_type","news"),item.get("confidence","Reported / unverified"),item.get("region","Global"),clean(item.get("vendor")),clean(item.get("product")),cve,clean(item.get("cvss")),clean(item.get("affected_versions")),clean(item.get("remediation")),int(bool(item.get("exploited"))),item.get("epss_score"),clean(item.get("event_date")),clean(item.get("published_at")),first_seen,now,first_seen,fingerprint(item["title"]))
        db.execute("""INSERT INTO incidents(id,title,summary,category,severity,primary_url,source_name,source_type,confidence,region,vendor,product,cve,cvss,affected_versions,remediation,exploited,epss_score,event_date,published_at,first_seen,last_seen,last_changed,fingerprint) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",vals)
        if link:
            db.execute("INSERT OR IGNORE INTO incident_sources VALUES (?,?,?,?)",(iid,link,clean(item.get("source_name"),100),now))
        db.execute("INSERT INTO incident_changes(incident_id,change_at,description,source_url) VALUES (?,?,?,?)",(iid,first_seen,"Imported historical record" if item.get("source_type")=="import" else "First captured from source",link))
        return "new"

def list_items(category=None,search=None,severity=None,limit=500,archived=None,offset=0):
    q="""SELECT incidents.*, COALESCE((SELECT MAX(id) FROM incident_changes
        WHERE incident_id=incidents.id), 0) AS change_id FROM incidents WHERE 1=1""";args=[]
    if category and category!="All": q+=" AND category=?";args.append(category)
    if severity and severity!="All": q+=" AND severity=?";args.append(severity)
    if search:
        q+=" AND (title LIKE ? OR summary LIKE ? OR cve LIKE ? OR source_name LIKE ?)"
        args.extend(["%"+search[:120]+"%"]*4)
    if archived is not None: q+=" AND archived=?";args.append(1 if archived else 0)
    q+=" ORDER BY first_seen DESC, id DESC LIMIT ? OFFSET ?";args.extend([min(max(int(limit),1),2000),max(0,int(offset))])
    with connect() as db:return [rowdict(x) for x in db.execute(q,args).fetchall()]

def details(item_id):
    with connect() as db:
        row=rowdict(db.execute("SELECT * FROM incidents WHERE id=?",(item_id,)).fetchone())
        if not row:return None
        row["sources"]=[rowdict(x) for x in db.execute("SELECT url,name,first_seen FROM incident_sources WHERE incident_id=? ORDER BY first_seen",(item_id,)).fetchall()]
        row["history"]=[rowdict(x) for x in db.execute("SELECT change_at,description,source_url FROM incident_changes WHERE incident_id=? ORDER BY id DESC",(item_id,)).fetchall()]
        row["organization"] = read_organization(db, item_id)
        return row

def read_organization(db, item_id):
    row = db.execute("SELECT favorite, tags FROM incident_organization WHERE incident_id=?", (item_id,)).fetchone()
    if row is None:
        return {"favorite": False, "tags": {}}
    return {"favorite": bool(row["favorite"]), "tags": json.loads(row["tags"])}

def list_favorites():
    with connect() as db:
        rows = db.execute("SELECT incident_id, tags FROM incident_organization WHERE favorite=1 ORDER BY incident_id")
        return {row["incident_id"]: json.loads(row["tags"]) for row in rows}

def update_organization(item_id, *, favorite=None, add_tag=None, remove_tag=None):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM incidents WHERE id=?", (item_id,)).fetchone():
            return None
        organization = read_organization(db, item_id)
        if favorite is not None:
            organization["favorite"] = favorite
        tags = organization["tags"]
        if remove_tag is not None:
            tags.pop(remove_tag.casefold(), None)
        if add_tag is not None:
            tags.setdefault(add_tag.casefold(), add_tag)
        db.execute("""
            INSERT INTO incident_organization(incident_id, favorite, tags) VALUES (?, ?, ?)
            ON CONFLICT(incident_id) DO UPDATE SET favorite=excluded.favorite, tags=excluded.tags
        """, (item_id, organization["favorite"], json.dumps(tags)))
        return organization

def stats():
    with connect() as db:
        count=db.execute("SELECT COUNT(*) AS c FROM incidents").fetchone()["c"]
        bycat={x["category"]:x["c"] for x in db.execute("SELECT category,COUNT(*) c FROM incidents GROUP BY category").fetchall()}
        byseverity={x["severity"]:x["c"] for x in db.execute("SELECT severity,COUNT(*) c FROM incidents GROUP BY severity").fetchall()}
        latest=rowdict(db.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone())
        last_change=db.execute("SELECT COALESCE(MAX(id),0) FROM incident_changes").fetchone()[0]
        return {"total":count,"categories":bycat,"severities":byseverity,"last_run":latest,"last_change_id":last_change}

def sources_status():
    with connect() as db:return [rowdict(x) for x in db.execute("SELECT * FROM feed_status ORDER BY name").fetchall()]

def source_checked(name,url,status,fetched,details_=""):
    with connect() as db:
        db.execute("INSERT INTO feed_status(name,url,last_checked,status,fetched,details) VALUES(?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET url=excluded.url,last_checked=excluded.last_checked,status=excluded.status,fetched=excluded.fetched,details=excluded.details",(name,url,utcnow(),status,fetched,clean(details_,350)))

def start_run():
    with connect() as db:
        cur=db.execute("INSERT INTO sync_runs(started) VALUES (?)",(utcnow(),));return cur.lastrowid

def end_run(run_id, counts):
    with connect() as db:
        db.execute("UPDATE sync_runs SET completed=?,new_items=?,updates=?,duplicates=?,error_count=? WHERE id=?",(utcnow(),counts.get("new",0),counts.get("updated",0),counts.get("duplicate",0),counts.get("errors",0),run_id))

def set_epss(scores):
    with connect() as db:
        for cve, val in scores.items(): db.execute("UPDATE incidents SET epss_score=? WHERE cve=?",(val,cve))

def import_legacy(payload):
    rows=payload.get("items",[]) if isinstance(payload,dict) else payload
    if not isinstance(rows,list) or len(rows)>5000:raise ValueError("Expected an items array (maximum 5,000)")
    counts={"new":0,"duplicate":0,"updated":0}
    for x in rows:
        if not isinstance(x,dict):continue
        rawsources=x.get("sources",[])
        links=[]
        for s in rawsources if isinstance(rawsources,list) else []:
            if isinstance(s,list) and len(s)>1:links.append((s[0],s[1]))
            elif isinstance(s,dict):links.append((s.get("label","Source"),s.get("url","")))
        title=clean(x.get("headline",x.get("title","")),350)
        if not title:continue
        cat={"Cyberattack":"Cyberattacks","Cyberattacks":"Cyberattacks","Vulnerability":"Vulnerabilities","Vulnerabilities":"Vulnerabilities","Data breach":"Data Breaches","Data Breaches":"Data Breaches","Technology":"Technology","Ransomware":"Ransomware"}.get(x.get("type",x.get("category")),"Cyberattacks")
        summary=" | ".join(clean(x.get(f,""),1400) for f in ("description","impact","action") if x.get(f)) or clean(x.get("summary"))
        url=next((u for _n,u in links if canonical_url(u)),"")
        result=upsert({"title":title,"summary":summary,"category":cat,"severity":x.get("severity","Info"),"url":url,"source_name":"Imported history (unverified)","source_type":"import","confidence":"Imported / not independently verified","published_at":x.get("date", ""),"import_first_seen":x.get("firstSeen",x.get("date", "")),"event_date":x.get("event_date",""),"region":x.get("region","Global"),"remediation":x.get("action","")})
        counts[result]+=1
        iid=calc_id({"title":title,"summary":summary,"category":cat,"url":url})
        with connect() as db:
            existing=match_existing(db,{"title":title,"summary":summary,"category":cat,"url":url}) or iid
            for name,uri in links:
                uri=canonical_url(uri)
                if uri:db.execute("INSERT OR IGNORE INTO incident_sources VALUES (?,?,?,?)",(existing,uri,clean(name,100),utcnow()))
    return counts
