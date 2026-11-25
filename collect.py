"""Coleta ofertas de PC com preços regionais brasileiros via IsThereAnyDeal."""
import datetime
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = Path(__file__).parent
key = os.environ.get("ITAD_API_KEY")
if not key:
    raise SystemExit("Configure o segredo ITAD_API_KEY no GitHub Actions.")

STORE_NAMES = {
    "steam": "Steam",
    "gog": "GOG",
    "nuuvem": "Nuuvem",
}

EPIC_SHOP_ID = 16  # Identificador da Epic Game Store no IsThereAnyDeal.

def get_json(endpoint, body=None, **query):
    request = Request(
        "https://api.isthereanydeal.com/" + endpoint + "?" + urlencode(query),
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "ITAD-API-Key": key,
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if body is not None else {}),
            "User-Agent": "GameDealsHub/1.1",
        },
    )
    try:
        with urlopen(request, timeout=45) as response:
            return json.load(response)
    except HTTPError as exc:
        print('Erro da API:', endpoint, query, exc.code, exc.read().decode('utf-8', errors='replace'))
        raise

def collect_pages(shop_ids):
    offset = 0
    # Percorre todo o feed; um limite de segurança impede loops da API.
    for _ in range(500):
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
        raise RuntimeError("A coleta excedeu o limite de segurança de páginas.")

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

priority_titles = json.loads(BASE.joinpath("priority-games.json").read_text(encoding="utf-8"))
identified = get_json("lookup/id/title/v1", body=priority_titles)
priority_ids = {game_id for game_id in identified.values() if game_id}
for title, game_id in identified.items():
    if not game_id:
        print("Título monitorado não identificado:", title)

def collect_priority():
    if not priority_ids:
        return
    prices = get_json(
        "games/prices/v3", body=sorted(priority_ids), country="BR",
        shops=",".join(map(str, stores_by_id)), deals="true",
    )
    for game in prices:
        info = get_json("games/info/v2", id=game["id"])
        for offer in game["deals"]:
            yield {**info, "id": game["id"], "deal": offer}

deals = []
seen = set()
for entries in [collect_priority(), *(collect_pages([shop_id]) for shop_id in stores_by_id)]:
    for entry in entries:
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
            "id": entry["id"],
            "featured": entry["id"] in priority_ids,
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
