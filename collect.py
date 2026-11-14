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

STORE_NAMES = {
    "steam": "Steam",
    "gog": "GOG",
    "nuuvem": "Nuuvem",
}

EPIC_SHOP_ID = 16  # Identificador da Epic Game Store no IsThereAnyDeal.

def get_json(endpoint, **query):
    request = Request(
        "https://api.isthereanydeal.com/" + endpoint + "?" + urlencode(query),
        headers={
            "ITAD-API-Key": key,
            "Accept": "application/json",
            "User-Agent": "GameDealsHub/1.1",
        },
    )
    with urlopen(request, timeout=45) as response:
        return json.load(response)

def collect_pages(shop_ids):
    offset = 0
    # Limita cada consulta a dez páginas e respeita o cursor da API.
    for _ in range(10):
        payload = get_json(
            "deals/v2", country="BR", limit=200, offset=offset,
            sort="-cut", shops=",".join(map(str, shop_ids)),
        )
        yield from payload["list"]
        if not payload["hasMore"]:
            return
        next_offset = payload["nextOffset"]
        if next_offset <= offset:
            raise ValueError("O cursor de ofertas não avançou.")
        offset = next_offset
    if payload["hasMore"]:
        print("Limite de páginas atingido para lojas:", shop_ids)

shops = get_json("service/shops/v1", country="BR")
stores_by_id = {
    shop["id"]: STORE_NAMES[shop["title"].strip().casefold()]
    for shop in shops
    if shop["title"].strip().casefold() in STORE_NAMES
}
if any(shop["id"] == EPIC_SHOP_ID for shop in shops):
    stores_by_id[EPIC_SHOP_ID] = "Epic Games"
if not stores_by_id:
    raise SystemExit("Nenhuma das lojas configuradas foi encontrada para o Brasil.")

# O feed retorna a melhor oferta por jogo. Consultar a Epic à parte
# mantém suas promoções mesmo quando outra loja tem um preço menor.
other_stores = [shop_id for shop_id, name in stores_by_id.items() if name != "Epic Games"]
epic_stores = [shop_id for shop_id, name in stores_by_id.items() if name == "Epic Games"]
if not epic_stores:
    print("Epic Games indisponível na lista de lojas para o Brasil.")

deals = []
seen = set()
for shop_ids in (other_stores, epic_stores):
    if not shop_ids:
        continue
    for entry in collect_pages(shop_ids):
        deal = entry.get("deal") or {}
        shop_id = (deal.get("shop") or {}).get("id")
        store = stores_by_id.get(shop_id)
        price = deal.get("price") or {}
        if not store or price.get("currency") != "BRL":
            continue
        amount = price.get("amount")
        if not isinstance(amount, (int, float)):
            continue
        identity = (entry["id"], store)
        if identity in seen:
            continue
        seen.add(identity)
        assets = entry.get("assets") or {}
        cover_url = next(
            (assets[size] for size in ("banner400", "banner600", "banner300", "banner145", "boxart")
             if isinstance(assets.get(size), str) and assets[size].startswith("https://")),
            None,
        )
        deals.append({
            "title": entry.get("title") or "Sem título",
            "game_type": entry.get("type"),
            "store": store,
            "price": amount,
            "regular_price": (deal.get("regular") or {}).get("amount"),
            "discount": deal.get("cut") or 0,
            "url": deal.get("url") or "",
            "expires_at": deal.get("expiry"),
            "cover_url": cover_url,
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
print("Ofertas coletadas:", len(deals), "| Epic Games:", sum(deal["store"] == "Epic Games" for deal in deals))
