"""Komplettering av mapping.json:
1. Godkända produkter utan Yahoo-serie på sin handelsplats: sök samma ISIN på Yahoo och godta en annan börs
   (t.ex. LSE i USD) om kursen, omräknad med växelkurs, stämmer inom 3 %.
2. Marknader utan träffar: prova alternativa sökord.
Kör efter mapper.py: python -E -s mapper_fix.py"""
import json
import os
import time
import urllib.parse

import mapper as M

HERE = os.path.dirname(os.path.abspath(__file__))
ALT_QUERIES = {
    "russell2000": ["Russell 2000"],
    "tin": ["Tin", "WisdomTree Tin"],
    "brent": ["Brent Crude", "WisdomTree Brent"],
    "cocoa": ["Cocoa"],
    "eur_govt": ["Euro Government Bond", "Core Euro Government"],
    "reit_world": ["Developed Markets Property", "Global REIT"],
}
FX = {}


def fx(a, b):
    """Kurs för 1 a uttryckt i b, från Yahoo."""
    if a == b:
        return 1.0
    a, b = ("GBP" if a == "GBp" else a), ("GBP" if b == "GBp" else b)
    key = a + b
    if key not in FX:
        meta = M.yahoo_meta(f"{a}{b}=X")
        FX[key] = meta.get("regularMarketPrice") if meta else None
        time.sleep(0.4)
    return FX[key]


def yahoo_isin(isin):
    d = M.get("https://query1.finance.yahoo.com/v1/finance/search?q=" + urllib.parse.quote(isin) + "&quotesCount=10&newsCount=0")
    return [q["symbol"] for q in (d or {}).get("quotes", []) if q.get("symbol")]


def attach_alt(rec):
    if not rec.get("eligible") or rec.get("yahoo") or not rec.get("isin") or not rec.get("avanzaLast"):
        return
    for sym in yahoo_isin(rec["isin"]):
        meta = M.yahoo_meta(sym)
        time.sleep(0.4)
        if not meta or not meta.get("regularMarketPrice"):
            continue
        cur = meta.get("currency")
        price = meta["regularMarketPrice"] / (100 if cur == "GBp" else 1)
        rate = fx("GBP" if cur == "GBp" else cur, rec["currency"])
        if not rate:
            continue
        ratio = price * rate / rec["avanzaLast"]
        if 0.97 <= ratio <= 1.03:
            rec["yahoo"] = sym
            rec["yahooCheck"] = round(ratio, 4)
            rec["yahooFirstTrade"] = meta.get("firstTradeDate")
            rec["yahooNote"] = f"kursserie från {sym} ({cur}), samma ISIN som Avanzas listning"
            print("  alternativ serie", rec["name"], sym, round(ratio, 3), flush=True)
            return


def main():
    path = os.path.join(HERE, "mapping.json")
    mp = json.load(open(path, encoding="utf-8"))
    seen = {p["orderbookId"] for v in mp["markets"].values() for p in v}
    for mid, qs in ALT_QUERIES.items():
        if any(p.get("eligible") for p in mp["markets"].get(mid, [])):
            continue
        for q in qs:
            for hit in M.avanza_search(q)[:8]:
                if hit["type"] not in ("EXCHANGE_TRADED_FUND", "CERTIFICATE") or hit["orderBookId"] in seen or M.LEVERAGED.search(hit["title"]):
                    continue
                d, page = M.avanza_detail(hit)
                time.sleep(0.4)
                if not d:
                    continue
                listing = d.get("listing") or {}
                lev = (d.get("keyIndicators") or {}).get("leverage", 1)
                direction = (d.get("keyIndicators") or {}).get("direction", "Lång")
                rec = {"orderbookId": hit["orderBookId"], "name": d.get("name"), "isin": d.get("isin"), "ticker": listing.get("tickerSymbol"),
                       "marketPlace": listing.get("marketPlaceName"), "currency": listing.get("currency"), "tradable": d.get("tradable"),
                       "leverage": lev, "direction": direction, "type": hit["type"], "avanzaUrl": page,
                       "spread": (d.get("quote") or {}).get("spread"), "valueTradedToday": (d.get("quote") or {}).get("totalValueTraded"),
                       "owners": (d.get("keyIndicators") or {}).get("numberOfOwners"), "avanzaLast": (d.get("quote") or {}).get("last"), "query": q}
                rec["eligible"] = rec["tradable"] == "BUYABLE_AND_SELLABLE" and lev in (1, 1.0, None) and direction in ("Lång", None)
                seen.add(hit["orderBookId"])
                sfx = M.SUFFIX.get(rec["marketPlace"])
                rec["yahoo"] = None
                if rec["eligible"] and sfx and rec["ticker"]:
                    sym = rec["ticker"].replace(" ", "-") + sfx
                    meta = M.yahoo_meta(sym)
                    if meta and meta.get("regularMarketPrice") and rec["avanzaLast"]:
                        ratio = meta["regularMarketPrice"] / (100 if meta.get("currency") == "GBp" else 1) / rec["avanzaLast"]
                        if 0.97 <= ratio <= 1.03:
                            rec["yahoo"], rec["yahooCheck"], rec["yahooFirstTrade"] = sym, round(ratio, 4), meta.get("firstTradeDate")
                mp["markets"].setdefault(mid, []).append(rec)
                print(mid, rec["name"], rec["marketPlace"], rec["tradable"], rec["yahoo"], flush=True)
    for mid, prods in mp["markets"].items():
        for rec in prods:
            attach_alt(rec)
    json.dump(mp, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in mp["markets"].values() for p in v if p.get("eligible") and p.get("yahoo"))
    print("godkända med kursserie:", ok)


if __name__ == "__main__":
    main()
