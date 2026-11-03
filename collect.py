"""Coleta ofertas de PC com preços regionais brasileiros via IsThereAnyDeal."""
import datetime
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

key = os.environ.get("ITAD_API_KEY")
if not key:
    raise SystemExit("Configure o segredo ITAD_API_KEY no GitHub Actions.")

params = urlencode({"country": "BR", "limit": 200, "sort": "-cut"})
url = "https://api.isthereanydeal.com/deals/v2?" + params
request = Request(url, headers={
    "ITAD-API-Key": key,
    "Accept": "application/json",
    "User-Agent": "GameDealsHub/1.0",
})
with urlopen(request, timeout=45) as response:
    payload = json.load(response)

stores = {
    "Steam": "Steam",
    "Epic Games Store": "Epic Games",
    "Epic Games": "Epic Games",
    "GOG": "GOG",
    "Nuuvem": "Nuuvem",
}
deals = []
for entry in payload.get("list", []):
    deal = entry.get("deal") or {}
    store = stores.get((deal.get("shop") or {}).get("name", ""))
    if not store:
        continue
    price = (deal.get("price") or {}).get("amount")
    regular = (deal.get("regular") or {}).get("amount")
    if not isinstance(price, (int, float)):
        continue
    deals.append({
        "title": entry.get("title") or "Sem título",
        "store": store,
        "price": price,
        "regular_price": regular,
        "discount": deal.get("cut") or 0,
        "url": deal.get("url") or "",
        "historical_low": False,
        "coupon": None,
    })

output = {
    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source": "IsThereAnyDeal",
    "country": "BR",
    "deals": deals,
}
Path(__file__).with_name("deals.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("Ofertas das lojas selecionadas:", len(deals))
