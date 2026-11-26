"""Coleta ofertas de PC com preços regionais brasileiros via IsThereAnyDeal."""
import argparse
import datetime
import json
import os
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

parser = argparse.ArgumentParser()
parser.add_argument("--interest-only", action="store_true")
args = parser.parse_args()
BASE = Path(__file__).parent
previous = {}
if args.interest_only:
    previous = json.loads(BASE.joinpath("deals.json").read_text(encoding="utf-8"))

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
    for attempt in range(6):
        time.sleep(1)
        try:
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 429 and attempt < 5:
                retry_after = exc.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = int(retry_after)
                elif retry_after:
                    retry_at = parsedate_to_datetime(retry_after)
                    delay = (retry_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                else:
                    delay = 60 * (attempt + 1)
                print("Limite da API; aguardando", max(1, delay), "segundos.")
                time.sleep(max(1, delay))
                continue
            print("Erro da API:", endpoint, query, exc.code)
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

popular_games = get_json("stats/most-popular/v1", limit=100)
wanted_games = get_json("stats/most-waitlisted/v1", limit=100)
popular_rank = {game["id"]: game["position"] for game in popular_games}
wanted_rank = {game["id"]: game["position"] for game in wanted_games}
ranked_games = {game["id"]: game for game in [*popular_games, *wanted_games]}

def collect_interest():
    tracked_ids = sorted(priority_ids | ranked_games.keys())
    for start in range(0, len(tracked_ids), 200):
        prices = get_json(
            "games/prices/v3", body=tracked_ids[start:start + 200], country="BR",
            shops=",".join(map(str, stores_by_id)), deals="true",
        )
        for game in prices:
            if not game["deals"]:
                continue
            known = next((deal for deal in previous.get("deals", []) if deal.get("id") == game["id"]), None)
            info = (
                {"title": known["title"], "type": known.get("game_type"),
                 "assets": {"banner400": known.get("cover_url")}}
                if known else get_json("games/info/v2", id=game["id"])
            )
            for offer in game["deals"]:
                yield {**info, "id": game["id"], "deal": offer}

deals_by_store = {
    (deal["id"], deal["store"]): {
        **deal,
        "featured": deal["id"] in priority_ids,
        "popularity_rank": popular_rank.get(deal["id"]),
        "wishlist_rank": wanted_rank.get(deal["id"]),
    }
    for deal in previous.get("deals", []) if deal.get("id")
}
# Remove preços antigos dos títulos consultados diretamente antes de substituí-los.
tracked_ids = priority_ids | ranked_games.keys()
if args.interest_only:
    deals_by_store = {key: deal for key, deal in deals_by_store.items() if key[0] not in tracked_ids}
feeds = [] if args.interest_only else [collect_pages([shop_id]) for shop_id in stores_by_id]
for entries in [*feeds, collect_interest()]:
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
        assets = entry.get("assets") or {}
        cover_url = next(
            (assets[size] for size in ("banner400", "banner600", "banner300", "banner145", "boxart")
             if isinstance(assets.get(size), str) and assets[size].startswith("https://")),
            None,
        )
        deals_by_store[identity] = {
            "id": entry["id"],
            "featured": entry["id"] in priority_ids,
            "popularity_rank": popular_rank.get(entry["id"]),
            "wishlist_rank": wanted_rank.get(entry["id"]),
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
        }

deals = list(deals_by_store.values())
on_sale_ids = {deal["id"] for deal in deals}
watch_games = [
    {"title": game["title"], "url": "https://isthereanydeal.com/game/" + game["slug"] + "/info/"}
    for game in wanted_games if game["id"] not in on_sale_ids and game.get("type") == "game"
][:6]

output = {
    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source": "IsThereAnyDeal",
    "country": "BR",
    "deals": deals,
    "watch_games": watch_games,
    "catalog_updated_at": previous.get("catalog_updated_at", previous.get("updated_at")) if args.interest_only else datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
Path(__file__).with_name("deals.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("Ofertas coletadas:", len(deals), "| Epic Games:", sum(deal["store"] == "Epic Games" for deal in deals))
