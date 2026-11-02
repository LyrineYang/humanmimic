#!/usr/bin/env python3
"""Local public-entry links and HTML structure; historical run links stay archival."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.ids=set(); self.errors=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:
            if attrs['id'] in self.ids: self.errors.append('Duplicate HTML id: '+attrs['id'])
            self.ids.add(attrs['id'])
        for key in ['href','src']:
            if key in attrs: self.links.append(attrs[key])
        if tag=='img' and not attrs.get('alt'): self.errors.append('Missing image alt text')


def anchors(path):
    if path.suffix=='.html':
        page=Page(); page.feed(path.read_text()); return page.ids
    ids=set(); counts={}
    for line in path.read_text().splitlines():
        if not re.match(r'^#{1,6} ',line): continue
        heading=re.sub(r'^#+\s+','',line).strip().lower()
        slug=re.sub(r'[^\w\- ]','',heading).replace(' ','-')
        n=counts.get(slug,0); counts[slug]=n+1
        ids.add(slug+('-'+str(n) if n else ''))
    return ids


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',type=Path,required=True); args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    files=[ROOT/'README.md',ROOT/'CONTRIBUTING.md',*(ROOT/'docs').glob('*.md'),ROOT/'website/index.html']
    errors=[]; checked=0; archive=[]
    for source in files:
        text=source.read_text()
        if source.suffix=='.html':
            page=Page(); page.feed(text); links=page.links; errors += [str(source.relative_to(ROOT))+': '+e for e in page.errors]
        else:
            links=re.findall(r'\[[^\]]*\]\(([^)]+)\)',text)
            links+=re.findall(r'<(?:img|a)\b[^>]*(?:src|href)="([^"]+)"',text)
        for link in links:
            parts=urlsplit(link.strip('<>'))
            if parts.scheme or parts.netloc: continue
            target=(source.parent/unquote(parts.path)).resolve() if parts.path else source
            if ROOT/'runs' in target.parents:
                archive.append(str(target)); continue
            checked+=1
            if not target.exists(): errors.append('{}: missing {}'.format(source.relative_to(ROOT),link))
            elif parts.fragment and target.suffix in ['.md','.html'] and unquote(parts.fragment) not in anchors(target):
                errors.append('{}: missing anchor {}'.format(source.relative_to(ROOT),link))
    result={'status':'failed' if errors else 'passed','files':len(files),'local_links_checked':checked,
            'historical_run_links_excluded':len(archive),'errors':errors,
            'scope':'Local links, anchors, HTML unique ids and image text; not browser rendering or remote publication'}
    (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2)); return bool(errors)


if __name__=='__main__': raise SystemExit(main())
