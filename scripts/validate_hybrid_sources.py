#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, html as html_module, json, re, time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
ROOT = Path(__file__).resolve().parents[1]
@dataclass
class HybridReport:
    source_id: str
    status: str
    search_results: int = 0
    chapters: int = 0
    pages: int = 0
    popular_results: int = 0
    genre_results: int = 0
    image_url: str | None = None
    error: str | None = None
    elapsed_seconds: float = 0.0
def _session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s=requests.Session();s.mount("https://",HTTPAdapter(max_retries=Retry(total=2,connect=2,read=2,status=2,backoff_factor=.75,status_forcelist=(408,425,429,500,502,503,504),allowed_methods=frozenset({"GET","HEAD"}),respect_retry_after_header=True)));return s
def _expand(value:str,variables:dict[str,str])->str:
    for k,v in variables.items(): value=value.replace("{{"+k+"}}",v).replace("{"+k+"}",v)
    return value
def _json_path(root:Any,path:str)->Any:
    current=root
    for part in path.replace("$.","").strip("$").split("."):
        if not part: continue
        if isinstance(current,dict): current=current.get(part)
        elif isinstance(current,list) and part.isdigit() and int(part)<len(current): current=current[int(part)]
        else: return None
    return current
def _headers(config):
    h=dict((config.get("network") or {}).get("headers") or {});h.setdefault("User-Agent","Mozilla/5.0 YomuhonSourceValidator/4.0");return h
def _route_url(config,route,variables):
    base=urljoin(config["baseURL"].rstrip("/")+"/",_expand(route["path"],variables).lstrip("/"));p=urlparse(base);q=parse_qsl(p.query,keep_blank_values=True);q += [(k,_expand(str(v),variables)) for k,v in (route.get("query") or {}).items()];return urlunparse(p._replace(query=urlencode(q)))
def _field(scope,field):
    if not field:return None
    sels=field.get("selectors") or ([field["selector"]] if field.get("selector") else []);c=[]
    if sels:
        for sel in sels:
            x=scope.select_one(sel)
            if x is not None:c.append(x)
    else:c.append(scope)
    attrs=field.get("attrs") or ([field["attr"]] if field.get("attr") else ["text"])
    for x in c:
        for attr in attrs:
            value=x.get_text(" ",strip=True) if attr=="text" else x.get(attr)
            if isinstance(value,str) and value.strip():
                if field.get("regex"):
                    m=re.search(field["regex"],value,re.I|re.S)
                    if not m:continue
                    value=m.group(1) if m.groups() else m.group(0)
                return html_module.unescape(re.sub(r"\s+"," ",value).strip())
    return None
def _canonical(config,url):
    p=urlparse(url);keep={x.lower() for x in ((config.get("identity") or {}).get("preserveQueryItems") or [])};q=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k.lower() in keep];return urlunparse(p._replace(query=urlencode(q),fragment=""))
def _html_list(config,text,selector):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(text,"html.parser");out=[];seen=set()
    for item in soup.select(selector["container"]):
        raw=_field(item,selector["url"]) or item.get("href");title=_field(item,selector["title"])
        if not raw or not title:continue
        url=_canonical(config,urljoin(config["baseURL"],raw))
        if url in seen:continue
        seen.add(url);out.append({"title":title,"url":url})
    return out
def _variables(operation,manga_url,manga_id):
    out={"mangaURL":manga_url,"mangaID":manga_id}
    for name,rule in (operation.get("variables") or {}).items():
        source=manga_url if rule.get("from")=="mangaURL" else manga_id if rule.get("from")=="mangaID" else "";value=None
        if rule.get("regex"):
            m=re.search(rule["regex"],source,re.I)
            if m:value=m.group(1) if m.groups() else m.group(0)
        elif source:value=source
        if value:out[name]=value
        elif rule.get("default") is not None:out[name]=str(rule["default"])
    return out
def _api_json(session,config,request,variables,timeout):
    base=request.get("baseURL") or config["baseURL"];url=urljoin(base.rstrip("/")+"/",_expand(request["path"],variables).lstrip("/"));q=[]
    for k,v in (request.get("query") or {}).items():
        if isinstance(v,bool):v="true" if v else "false"
        q.append((k,_expand(str(v),variables)))
    r=session.get(url,params=q,headers=_headers(config),timeout=timeout);r.raise_for_status();return r.json()
def _pages(config,text,chapter_url):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(text,"html.parser");out=[];seen=set()
    for ex in config["selectors"]["pages"]["extractors"]:
        if ex["type"]!="css":continue
        for e in soup.select(ex.get("selector","")):
            for attr in ex.get("attrs",["data-src","src"]):
                raw=e.get(attr)
                if isinstance(raw,str) and raw.strip():
                    u=urljoin(chapter_url,raw.strip())
                    if u not in seen:seen.add(u);out.append(u)
                    break
    return out
def _verify_image(session,url,config,timeout,referer):
    h=_headers(config);h["Referer"]=referer;h["Range"]="bytes=0-2047";r=session.get(url,headers=h,timeout=timeout,stream=True);r.raise_for_status();next(r.iter_content(chunk_size=256),b"");r.close()
def run_hybrid_for_main(entry,config,test,timeout,report_type=HybridReport):
    report=report_type(source_id=entry["id"],status="failed");started=time.monotonic();session=_session()
    try:
        query=(test.get("probe") or {}).get("query") or test["queries"][0];u=_route_url(config,config["routes"]["search"],{"query":query});r=session.get(u,headers=_headers(config),timeout=timeout);r.raise_for_status();results=_html_list(config,r.text,config["selectors"]["search"]);report.search_results=len(results)
        if len(results)<test["expected"]["minSearchResults"]:raise RuntimeError("Search returned too few results")
        manga=results[0];d=session.get(manga["url"],headers=_headers(config),timeout=timeout);d.raise_for_status();op=config["api"]["chapters"];root=_api_json(session,config,op["request"],_variables(op,manga["url"],manga["url"]),timeout);chapters=_json_path(root,op["itemsPath"]) or [];report.chapters=len(chapters)
        if len(chapters)<test["expected"]["minChapters"]:raise RuntimeError("Chapter API returned too few chapters")
        first=chapters[-1] if op.get("sort")=="numberAscending" else chapters[0];raw=_json_path(first,op.get("urlPath") or op["idPath"])
        if not isinstance(raw,str) or not raw:raise RuntimeError("Chapter API did not return a reader URL")
        chapter_url=urljoin(config["baseURL"],raw);reader=session.get(chapter_url,headers=_headers(config),timeout=timeout);reader.raise_for_status();pages=_pages(config,reader.text,chapter_url);report.pages=len(pages)
        if len(pages)<test["expected"]["minPages"]:raise RuntimeError("Reader returned too few pages")
        report.image_url=pages[0];_verify_image(session,pages[0],config,timeout,chapter_url);minimum=(test.get("discover") or {}).get("minPopularResults")
        if minimum is not None:
            pu=_route_url(config,config["routes"]["popular"],{});pr=session.get(pu,headers=_headers(config),timeout=timeout);pr.raise_for_status();items=_html_list(config,pr.text,config["selectors"]["popular"]);report.popular_results=len(items)
            if len(items)<minimum:raise RuntimeError("Popular returned too few results")
        report.status="passed"
    except Exception as exc:report.error=f"{type(exc).__name__}: {exc}"
    finally:report.elapsed_seconds=round(time.monotonic()-started,3);session.close()
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo",type=Path,default=ROOT);p.add_argument("--source",action="append",default=[]);p.add_argument("--timeout",type=float,default=20);p.add_argument("--report",type=Path);a=p.parse_args();index=json.loads((a.repo/"index.json").read_text());wanted=set(a.source);entries=[e for e in index["sources"] if e["id"].startswith("webtoon_") and (not wanted or e["id"] in wanted)];reports=[]
    for entry in entries:
        fn=urlparse(entry["url"]).path.rsplit("/",1)[-1];config=json.loads((a.repo/"sources"/fn).read_text());test=json.loads((a.repo/"tests"/f"{Path(fn).stem}.test.json").read_text());report=run_hybrid_for_main(entry,config,test,a.timeout);reports.append(report);print(("LIVE OK" if report.status=="passed" else "LIVE FAIL")+f": {report.source_id} | search={report.search_results} chapters={report.chapters} pages={report.pages} popular={report.popular_results} time={report.elapsed_seconds}s"+(f" | {report.error}" if report.error else ""))
    if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"reports":[asdict(r) for r in reports]},ensure_ascii=False,indent=2)+"\n")
    return 1 if any(r.status!="passed" for r in reports) else 0
if __name__=="__main__":raise SystemExit(main())
