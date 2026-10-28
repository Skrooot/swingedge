"""Tradable Instrument Mapper: kopplar varje marknad i universe.json till köpbara Avanza-produkter.

För varje sökord: Avanzas offentliga sök- och produktdata (samma som avanza.se använder) ger ISIN, handelsplats,
valuta, status och hävstång. Produkten översätts till en Yahoo-symbol och godkänns bara om Yahoos senaste kurs
stämmer med Avanzas inom 3 %, så att rätt kursserie används i forskningen.
Skriver mapping.json. Kör: python -E -s mapper.py
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "SwingEdge-research/1.0 (+https://github.com/Skrooot/swingedge)"}
SUFFIX = {"Xetra": ".DE", "London Stock Exchange": ".L", "Stockholmsbörsen": ".ST", "First North Stockholm": ".ST",
          "SIX Swiss Exchange": ".SW", "Euronext Amsterdam": ".AS", "Borsa Italiana": ".MI", "Euronext Paris": ".PA"}
LEVERAGED = re.compile(r"\b(bull|bear|short|lev|leveraged|[2-9]x|x[2-9]|daily|inverse|mini)\b", re.I)


def get(url, data=None):
    headers = dict(UA)
    if data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return None
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def avanza_search(q):
    d = get("https://www.avanza.se/_api/search/filtered-search",
            {"query": q, "searchFilter": {"types": []}, "pagination": {"from": 0, "size": 8}})
    return (d or {}).get("hits", [])


def avanza_detail(hit):
    oid = hit["orderBookId"]
    if hit["type"] == "EXCHANGE_TRADED_FUND":
        d = get(f"https://www.avanza.se/_api/market-etf/{oid}")
        page = f"https://www.avanza.se/borshandlade-produkter/etf-torg/om-fonden.html/{oid}/{hit['urlSlugName']}"
    else:
        d = get(f"https://www.avanza.se/_api/market-guide/certificate/{oid}")
        page = f"https://www.avanza.se/borshandlade-produkter/certifikat-torg/om-certifikatet.html/{oid}/{hit['urlSlugName']}"
    return d, page


def yahoo_meta(sym):
    d = get("https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym) + "?range=5d&interval=1d")
    try:
        return d["chart"]["result"][0]["meta"]
    except Exception:
        return None


def main():
    uni = json.load(open(os.path.join(HERE, "universe.json"), encoding="utf-8"))
    out, seen = {}, set()
    for m in uni["markets"]:
        prods = []
        for q in m["productQueries"]:
            for hit in avanza_search(q)[:8]:
                if hit["type"] not in ("EXCHANGE_TRADED_FUND", "CERTIFICATE") or hit["orderBookId"] in seen:
                    continue
                if LEVERAGED.search(hit["title"]):
                    continue
                d, page = avanza_detail(hit)
                time.sleep(0.4)
                if not d:
                    continue
                lev = (d.get("keyIndicators") or {}).get("leverage", 1)
                direction = (d.get("keyIndicators") or {}).get("direction", "Lång")
                listing = d.get("listing") or {}
                mkt = listing.get("marketPlaceName", "")
                rec = {
                    "orderbookId": hit["orderBookId"], "name": d.get("name"), "isin": d.get("isin"),
                    "ticker": listing.get("tickerSymbol"), "marketPlace": mkt, "currency": listing.get("currency"),
                    "tradable": d.get("tradable"), "leverage": lev, "direction": direction, "type": hit["type"],
                    "avanzaUrl": page, "spread": (d.get("quote") or {}).get("spread"),
                    "valueTradedToday": (d.get("quote") or {}).get("totalValueTraded"),
                    "owners": (d.get("keyIndicators") or {}).get("numberOfOwners"),
                    "avanzaLast": (d.get("quote") or {}).get("last"),
                    "query": q,
                }
                seen.add(hit["orderBookId"])
                ok = rec["tradable"] == "BUYABLE_AND_SELLABLE" and (lev in (1, 1.0, None)) and direction in ("Lång", None)
                rec["eligible"] = bool(ok)
                rec["reason"] = None if ok else f"status {rec['tradable']}, hävstång {lev}, riktning {direction}"
                sfx = SUFFIX.get(mkt)
                if ok and sfx and rec["ticker"]:
                    sym = rec["ticker"].replace(" ", "-") + sfx
                    meta = yahoo_meta(sym)
                    time.sleep(0.5)
                    if meta and meta.get("regularMarketPrice") and rec["avanzaLast"]:
                        p = meta["regularMarketPrice"] / (100 if meta.get("currency") == "GBp" else 1)
                        ratio = p / rec["avanzaLast"]
                        rec["yahoo"] = sym if 0.97 <= ratio <= 1.03 else None
                        rec["yahooCheck"] = round(ratio, 4)
                        rec["yahooFirstTrade"] = meta.get("firstTradeDate")
                    else:
                        rec["yahoo"] = None
                        rec["yahooCheck"] = None
                elif ok:
                    rec["yahoo"] = None
                    rec["reason"] = f"ingen kursserie för handelsplatsen {mkt}"
                prods.append(rec)
                print(m["id"], hit["title"], mkt, rec["tradable"], rec.get("yahoo"), rec.get("yahooCheck"), flush=True)
        out[m["id"]] = prods
    json.dump({"verified": time.strftime("%Y-%m-%d"), "markets": out}, open(os.path.join(HERE, "mapping.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
