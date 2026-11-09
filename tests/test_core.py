import os
import tempfile
from pathlib import Path
from app import store, ingest

def setup_function():
    folder=Path(tempfile.mkdtemp(prefix="cti-tests-"))
    store.DB_PATH=str(folder/"test.db")
    store.init_db()

def test_canonical_url_tracking_parameters():
    assert store.canonical_url("https://example.com/story/?utm_source=x&foo=1#tag")=="https://example.com/story?foo=1"

def item(**kw):
    return {"title":"New Apache vulnerability CVE-2026-11111 exploited","summary":"A vulnerability in server","category":"Vulnerabilities","severity":"High","url":"https://example.com/item?utm_campaign=abc","source_name":"Example","source_type":"news","published_at":"2026-11-09",**kw}

def test_same_url_duplicate():
    assert store.upsert(item())=="new"
    assert store.upsert(item())=="duplicate"
    assert store.stats()["total"]==1

def test_cve_dedup_across_sources():
    store.upsert(item())
    x=item();x["title"]="Different article about CVE-2026-11111";x["url"]="https://other.org/another-article"
    assert store.upsert(x)=="duplicate"
    assert len(store.details("CVE-2026-11111")["sources"])==2

def test_official_confirmed_exploitation_updates():
    store.upsert(item())
    x=item();x["source_name"]="CISA KEV";x["source_type"]="official";x["exploited"]=True
    assert store.upsert(x,official_update=True)=="updated"
    assert store.upsert(x,official_update=True)=="duplicate"
    d=store.details("CVE-2026-11111")
    assert d["updates"]==1 and d["exploited"]==1

def test_category_logic():
    assert ingest.category_for("Ransomware hits firm","")=="Ransomware"
    assert ingest.category_for("Customer data breach","")=="Data Breaches"
    assert ingest.category_for("CVE-2026-11111 patch","")=="Vulnerabilities"

def test_import_duplicate():
    payload={"items":[{"headline":"Historic cyberattack","description":"Compromised system","severity":"High","type":"Cyberattack","sources":[["Source","https://example.org/history"]]}]*2}
    result=store.import_legacy(payload)
    assert result["new"]==1 and result["duplicate"]==1


def test_distinct_cisa_kev_ids_not_collapsed():
    base={"title":"CVE-2026-22222 Foo bug", "summary":"Known exploited", "category":"Vulnerabilities", "severity":"High", "url":"https://www.cisa.gov/known-exploited-vulnerabilities-catalog", "source_name":"CISA KEV", "source_type":"official", "cve":"CVE-2026-22222", "exploited":True}
    assert store.upsert(base)=="new"
    second={**base,"title":"CVE-2026-33333 Bar bug","cve":"CVE-2026-33333"}
    assert store.upsert(second)=="new"
    assert store.stats()["total"]==2

def test_rss_reader():
    from app.rss import read_feed
    data=b'<rss><channel><item><title>Item 1</title><link>https://example.com/i</link><description>Some news</description><pubDate>Mon, 09 Nov 2026 01:00:00 GMT</pubDate></item></channel></rss>'
    items=read_feed(data)
    assert len(items)==1 and items[0]['title']=='Item 1'
    assert 'https://' in items[0]['link']
    try:read_feed(b'<!DOCTYPE foo><rss/>')
    except ValueError:pass
    else:assert False,'DTD must be rejected'
