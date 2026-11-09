"""Sources with verifiable public feeds. Link-only observatories are not scraped."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Source:
    name: str
    url: str
    category: str = "auto"
    source_type: str = "news"   # official / research / news
    watch: bool = True

FEEDS = [
    Source("CISA Cybersecurity Advisories", "https://www.cisa.gov/cybersecurity-advisories/all.xml", "auto", "official"),
    Source("CERT-FR Alerts", "https://cert.cyber.gouv.fr/alerte/feed/", "Vulnerabilities", "official"),
    Source("CERT-FR Threats", "https://cert.cyber.gouv.fr/menace/feed/", "auto", "official"),
    Source("CERT-FR Advisories", "https://cert.cyber.gouv.fr/avis/feed/", "Vulnerabilities", "official"),
    Source("SANS Internet Storm Center", "https://isc.sans.edu/rssfeed_full.xml", "auto", "research"),
    Source("watchTowr Labs", "https://labs.watchtowr.com/rss/", "Vulnerabilities", "research"),
    Source("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "auto", "news"),
    Source("The Record", "https://therecord.media/feed", "auto", "news"),
    Source("SecurityWeek", "https://www.securityweek.com/feed/", "auto", "news"),
    Source("Krebs on Security", "https://krebsonsecurity.com/feed/", "auto", "news"),
]

EXTERNAL = [
    {"name":"watchTowr Intelligence","url":"https://watchtowr.com/intelligence/","note":"Research portal. watchTowr Labs RSS is ingested; this page is a link, not a guaranteed automatic feed."},
    {"name":"Cloudflare Radar","url":"https://radar.cloudflare.com/security","note":"Global attack trends; API integration would require additional setup."},
    {"name":"GreyNoise","url":"https://viz.greynoise.io/","note":"Internet scanning context; API authentication may be required."},
    {"name":"Ransomware.live","url":"https://www.ransomware.live/","note":"Ransomware claims; no automated victim ingestion in this version."},
    {"name":"NCSC Switzerland","url":"https://www.ncsc.admin.ch/","note":"Swiss national security alerts; direct feed not included in this version."},
    {"name":"ENISA","url":"https://www.enisa.europa.eu/","note":"European strategic threat information."},
    {"name":"FIRST EPSS","url":"https://www.first.org/epss/","note":"CVE-specific exploitation probability is enriched through the public API."},
]
