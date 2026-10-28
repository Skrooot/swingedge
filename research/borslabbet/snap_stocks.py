"""Hämtar dagens nyckeltal för appens aktieuniversum från Avanza (samma anrop som appens Factor Scanner).
Används för att kontrollera sektorfilter och rangordning. Skriver data/stocks_snapshot.json."""
import json, sys, time, collections
sys.stdout.reconfigure(encoding="utf-8")
import av
U = json.load(open("C:/Users/fredrik/android-build/swingedge/app/src/main/assets/stock_universe.json", encoding="utf-8"))["stocks"]
out = []
for s in U:
    try: g = av.get(f"https://www.avanza.se/_api/market-guide/stock/{s['id']}")
    except Exception as e: print("fel", s["name"], e); continue
    out.append({"id": s["id"], "name": s["name"], "list": g.get("listing", {}).get("marketListName"), "sectors": [x["sectorName"] for x in g.get("sectors", [])],
                "k": g.get("keyIndicators"), "h": g.get("historicalClosingPrices"), "q": {k: g.get("quote", {}).get(k) for k in ("last", "spread", "totalValueTraded")}})
    time.sleep(0.2)
json.dump(out, open("data/stocks_snapshot.json", "w", encoding="utf-8"), ensure_ascii=False)
c = collections.Counter(x for o in out for x in o["sectors"][-1:])
print(len(out)); print(c.most_common(40))
