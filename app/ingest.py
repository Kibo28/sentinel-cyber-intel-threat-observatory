"""Feed ingestion: source-aware triage, deduplication and minimal EPSS enrichment."""
from collections import Counter
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from threading import Lock
import os
import re
import httpx
from bs4 import BeautifulSoup
from .rss import read_feed
from . import store
from . import notifications, preferences
from .public_feed import read_public_feed

CISA_KEV="https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CISA_FALLBACK="https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"
CLIENT_HEADERS={"User-Agent":"CTIObservatory/1.0 (+local self-hosted intelligence aggregator; RSS/CISA feeds)","Accept":"application/json,application/rss+xml,application/atom+xml,application/xml,text/xml,*/*"}
LOCK=Lock()
STATE={"running":False,"started":None,"finished":None,"counts":None}
KEYWORDS=re.compile(r"ransomware|malware|cyberattac|cyberattaque|breach|data leak|fuite de donn|exfiltrat|compromis|hacker|hacking|intrusion|phishing|credential|vulnerab|vulnérab|cve-\d|zero.day|0.day|exploited|exploitée|critical flaw|faille|patch bypass|authentication bypass|contournement|supply.chain|supply chain|espionage|espionnage|botnet|ddos|securit[ye]|sécurité|rootkit|backdoor|cryptojack|remote code execution|rce|attack surface|attaque|ot security|ssh|privilege escalation|élévation de privilège|ai agent", re.I)
HIGH_RE=re.compile(r"ransomware|actively exploite|exploitation active|0.day|zero.day|pre.auth|unauthenticated|auth(?:entication)? bypass|contournement de l.auth|remote code execution|exécution de code arbitraire|critical|critique|massive breach|millions of|supply.chain|incident majeur|high severity",re.I)
CRIT_RE=re.compile(r"cvss\s*(?:score)?\s*[:=]?\s*(?:9\.[0-9]|10\.0)|critical zero.day|critique exploitée",re.I)
BREACH_RE=re.compile(r"breach|fuite de donn|data leak|personal data|stolen data|exfiltrat|données personnelles|information (?:was )?exposed|exposed (?:customer|user) data",re.I)
RANSOM_RE=re.compile(r"ransomware|rançongiciel|extortion gang|ransom attack",re.I)
VULN_RE=re.compile(r"cve-\d{4}-\d{4,}|vulnerab|vulnérab|zero.day|0.day|critical flaw|security flaw|patch bypass|authentication bypass|contournement de l.auth|remote code execution|exécution de code arbitraire|faille|correctif de sécurité|privilege escalation",re.I)
TECH_RE=re.compile(r"artificial intelligence|\bAI\b|LLM|defensive technolog|threat research|novel technique|new technique|new tool|malware research|agentic|cybersecurity research|security research",re.I)

def extract_text(raw,limit=1700):
    text=BeautifulSoup(str(raw or ""),"html.parser").get_text(" ",strip=True)
    return re.sub(r"\s+"," ",unescape(text))[:limit]

def parse_date(entry):
    value=entry.get("published", "")
    if not value:return ""
    try:
        date=parsedate_to_datetime(value)
        return date.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError,TypeError):
        try:
            date=datetime.fromisoformat(value.replace("Z","+00:00"))
            if date.tzinfo is None:date=date.replace(tzinfo=timezone.utc)
            return date.astimezone(timezone.utc).isoformat(timespec="seconds")
        except (ValueError,TypeError): return ""

def category_for(title,summary,default="auto"):
    if default!="auto":return default
    text=title+" "+summary
    if RANSOM_RE.search(text):return "Ransomware"
    if BREACH_RE.search(text):return "Data Breaches"
    if VULN_RE.search(text):return "Vulnerabilities"
    if TECH_RE.search(text):return "Technology"
    return "Cyberattacks"

def severity_for(title,summary,source_type="news"):
    text=title+" "+summary
    if CRIT_RE.search(text):return "Critical"
    if HIGH_RE.search(text):return "High"
    return "Medium" if source_type=="official" else "Info"

def feed_items(source,client,now,days):
    entries=read_feed(read_public_feed(client, source.url))
    floor=now-timedelta(days=days)
    items=[]
    for entry in entries[:100]:
        title=extract_text(entry.get("title",""),350)
        summary=extract_text(entry.get("summary",entry.get("description","")))
        if not title or not KEYWORDS.search(title+" "+summary):continue
        published=parse_date(entry)
        if published:
            try:
                if datetime.fromisoformat(published)<floor:continue
            except ValueError:pass
        # CERT-FR generic advisories are frequent; focus on potentially serious ones.
        if source.name=="CERT-FR Advisories" and not (HIGH_RE.search(title+" "+summary) or store.CVEPAT.search(title+" "+summary)):continue
        url=store.canonical_url(entry.get("link",""))
        if not url: continue
        cat=category_for(title,summary,source.category)
        items.append({"title":title,"summary":summary,"category":cat,"severity":severity_for(title,summary,source.source_type),"url":url,"source_name":source.name,"source_type":source.source_type,"confidence":{"official":"Official publication","research":"Security research / independently validate impact"}.get(source.source_type,"Reported / verify against primary source"),"published_at":published,"region":"France" if source.name.startswith("CERT-FR") else "Global","remediation":"Read the linked advisory and validate affected assets, patches and mitigations." if cat=="Vulnerabilities" else "Review source evidence and assess exposure or downstream impact."})
    return items

def kev_items(client,now,days):
    errors=[]
    for url in [CISA_KEV,CISA_FALLBACK]:
        try:
            resp=client.get(url);resp.raise_for_status()
            if len(resp.content)>9_000_000:raise ValueError("KEV catalog size unexpectedly large")
            document=resp.json()
            rows=document.get("vulnerabilities",[])
            if not isinstance(rows,list):raise ValueError("Unexpected KEV JSON schema")
            floor=(now-timedelta(days=days)).date().isoformat()
            values=[]
            for row in rows:
                if row.get("dateAdded","")<floor:continue
                cve=row.get("cveID","")
                if not store.CVEPAT.fullmatch(cve):continue
                vendor=row.get("vendorProject","")
                product=row.get("product","")
                summary=row.get("shortDescription","")
                title=f"{cve}: {vendor} {product} — {row.get('vulnerabilityName','Known exploited vulnerability')}"
                values.append({"title":title[:350],"summary":summary,"category":"Vulnerabilities","severity":"High","url":"https://www.cisa.gov/known-exploited-vulnerabilities-catalog","source_name":"CISA KEV","source_type":"official","confidence":"CISA lists this vulnerability as known exploited","published_at":row.get("dateAdded",""),"event_date":row.get("dateAdded",""),"vendor":vendor,"product":product,"cve":cve,"exploited":True,"remediation":row.get("requiredAction","") or "Follow the vendor instructions to remediate the vulnerability.","region":"Global"})
            return values,url
        except Exception as e:errors.append(f"{type(e).__name__}: {str(e)[:130]}")
    raise ValueError("Both official CISA and official GitHub mirror retrieval failed: "+"; ".join(errors))

def enrich_epss(client,cves):
    values={}
    for start in range(0,min(len(cves),160),60):
        subset=cves[start:start+60]
        try:
            r=client.get("https://api.first.org/data/v1/epss",params={"cve":",".join(subset)})
            r.raise_for_status()
            for v in r.json().get("data",[]):
                if store.CVEPAT.fullmatch(v.get("cve","")):
                    score=float(v["epss"])
                    if 0<=score<=1:values[v["cve"].upper()]=score
        except Exception:pass  # optional enrichment: no fabricated value
    if values:store.set_epss(values)
    return len(values)

def sync_all():
    if not LOCK.acquire(blocking=False):return {"status":"already-running"}
    counts=Counter(new=0,updated=0,duplicate=0,errors=0)
    now=datetime.now(timezone.utc)
    STATE.update({"running":True,"started":now.isoformat(timespec="seconds"),"counts":None})
    run_id=None
    try:
        run_id=store.start_run()
        days=max(1,min(int(os.environ.get("CTI_LOOKBACK_DAYS","7")),60))
        config=preferences.source_config()
        findings=[]
        newcves=[]
        limits=httpx.Limits(max_keepalive_connections=0)
        with httpx.Client(headers=CLIENT_HEADERS,timeout=httpx.Timeout(20.0,connect=8.0),
                          follow_redirects=True,trust_env=False,limits=limits) as client:
            for source in config.feeds:
                if not source.enabled:
                    continue
                try:
                    items=feed_items(source,client,now,days)
                    for item in items:
                        out=store.upsert(item)
                        counts[out]+=1
                        if out=="new" and len(findings)<10:findings.append((item,out))
                        if out=="new" and store.CVEPAT.search(item["title"]):newcves += store.CVEPAT.findall(item["title"])
                    store.source_checked(source.name,source.url,"ok",len(items))
                except Exception as ex:
                    counts["errors"]+=1
                    store.source_checked(source.name,source.url,"error",0,f"{type(ex).__name__}: {str(ex)[:160]}")
            if config.kev_enabled:
                try:
                    items,used_url=kev_items(client,now,days)
                    for item in items:
                        out=store.upsert(item,official_update=True);counts[out]+=1
                        if out!="duplicate" and len(findings)<10:findings.append((item,out))
                        if out=="new":newcves.append(item["cve"])
                    store.source_checked("CISA KEV",used_url,"ok",len(items))
                except Exception as ex:
                    counts["errors"]+=1
                    store.source_checked("CISA KEV",CISA_KEV,"error",0,str(ex))
            if config.epss_enabled:
                enrich_epss(client,list(dict.fromkeys(newcves)))
        if preferences.collection_settings().email_enabled:
            notifications.send_digest(counts,findings)
        return {"status":"complete",**dict(counts)}
    except Exception as ex:
        counts["errors"]+=1
        return {"status":"failed","error":str(ex),**dict(counts)}
    finally:
        try:
            if run_id:store.end_run(run_id,counts)
        finally:
            STATE.update({"running":False,"finished":store.utcnow(),"counts":dict(counts)})
            LOCK.release()
