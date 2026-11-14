"""Enriquece ofertas com gêneros e ano via RAWG, sem inventar correspondências."""
import json, os, re, time, unicodedata
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE=Path(__file__).parent
data_path=BASE/"deals.json"
cache_path=BASE/"metadata_cache.json"
key=os.getenv("RAWG_API_KEY","").strip()
if not key:
    print("RAWG_API_KEY ausente; mantendo dados existentes sem enriquecer.")
    raise SystemExit(0)

data=json.loads(data_path.read_text(encoding="utf-8"))
try:
    cache=json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    if not isinstance(cache,dict):
        raise ValueError("Cache deve ser um objeto JSON")
except (ValueError, OSError) as exc:
    print("Cache inválido; reconstruindo:", type(exc).__name__)
    cache={}
def normalize(s):
    s=unicodedata.normalize("NFKD",s).casefold()
    return re.sub(r"[^a-z0-9]+"," ", "".join(c for c in s if not unicodedata.combining(c))).strip()
def lookup(title):
    query=urlencode({"key":key,"search":title,"search_exact":"true","page_size":5})
    req=Request("https://api.rawg.io/api/games?"+query,headers={"User-Agent":"GameDealsHub/1.1"})
    with urlopen(req,timeout=20) as response: results=json.load(response).get("results",[])
    matches=[x for x in results if normalize(x.get("name",""))==normalize(title)]
    if len(matches)!=1: return {"genres":[],"release_year":None,"status":"unmatched"}
    item=matches[0]
    released=item.get("released") or ""
    return {"genres":sorted({g["name"] for g in item.get("genres",[]) if g.get("name")}),
            "release_year":int(released[:4]) if re.match(r"^\d{4}-",released) else None,
            "status":"matched","rawg_url":"https://rawg.io/games/"+item["slug"] if item.get("slug") else None}

new_queries=0
for deal in data.get("deals",[]):
    title=deal["title"]
    if title not in cache and new_queries<80:
        try:
            cache[title]=lookup(title)
            new_queries+=1
            time.sleep(0.15)
        except Exception as exc:
            print("Não foi possível consultar metadados de",title,":",type(exc).__name__)
            continue
    info=cache.get(title,{})
    deal["genres"]=info.get("genres",[])
    deal["release_year"]=info.get("release_year")
    if info.get("status")=="matched": deal["metadata_source"]="RAWG"
cache_path.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding="utf-8")
data_path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
print("Metadados consultados nesta execução:",new_queries)
