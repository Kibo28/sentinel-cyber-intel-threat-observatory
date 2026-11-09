"""Restricted RSS/Atom parser using Python stdlib; rejects DTD/entity declarations."""
import xml.etree.ElementTree as ET

def field(element,*tags):
    for tag in tags:
        for node in element.iter():
            if node is element:continue
            if node.tag.rsplit('}',1)[-1].lower()==tag.lower():
                content=''.join(node.itertext()).strip()
                if content:return content
    return ''

def read_feed(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('DTD/entity declarations are not permitted in RSS feeds')
    root=ET.fromstring(data)
    root_tag=root.tag.rsplit('}',1)[-1].lower()
    entries=[]
    if root_tag in ('rss','rdf'):
        elements=[x for x in root.iter() if x.tag.rsplit('}',1)[-1].lower()=='item']
        for e in elements:
            entries.append({
                'title':field(e,'title'),
                'summary':field(e,'description','summary','encoded','content'),
                'link':field(e,'link','guid'),
                'published':field(e,'pubDate','date','published','updated'),
            })
    elif root_tag=='feed':
        elements=[x for x in root if x.tag.rsplit('}',1)[-1].lower()=='entry']
        for e in elements:
            links=[x for x in e.iter() if x.tag.rsplit('}',1)[-1].lower()=='link']
            link=next((x.get('href','') for x in links if x.get('rel','alternate')=='alternate' and x.get('href')), '')
            entries.append({
                'title':field(e,'title'),
                'summary':field(e,'summary','content'),
                'link':link,
                'published':field(e,'published','updated'),
            })
    else: raise ValueError('Unexpected RSS/Atom root element')
    return entries
