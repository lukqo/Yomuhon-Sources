#!/usr/bin/env python3
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser();p.add_argument("--repo",type=Path,default=Path.cwd());p.add_argument("--source",action="append",default=[]);p.add_argument("--all",action="store_true");a=p.parse_args();path=a.repo/"index.json";data=json.loads(path.read_text());wanted=set(a.source);changed=[]
for entry in data["sources"]:
    if entry["id"].startswith("webtoon_") and (a.all or entry["id"] in wanted):entry["enabled"]=True;entry["status"]="testing";changed.append(entry["id"])
if not changed:raise SystemExit("No WEBTOON sources selected")
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n");print("Enabled: "+", ".join(changed))
