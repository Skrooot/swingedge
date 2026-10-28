"""Bygger appens aktieuniversum (Large + Mid Cap Stockholm, ett aktieslag per bolag) med Avanzas orderbok-id.
Skriver swingedge/app/src/main/assets/stock_universe.json."""
import json, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
import av
src = open("C:/Users/fredrik/android-build/kryptosentiment/www/stocks.js", encoding="utf-8").read()
rows = re.findall(r'\["([A-Z0-9-]+\.ST)", "([^"]+)", "([LM])"', src)
by = {}
for sym, name, seg in rows:
    base = re.sub(r"\s+(A|B|C|D|SDB|ser\. ?[AB])$", "", name).strip()
    if base not in by or sym.endswith("-B.ST"): by[base] = (sym, name, seg)
out, miss = [], []
for base, (sym, name, seg) in sorted(by.items()):
    tick = sym[:-3].replace("-", " ")
    hit = None
    for q in (tick, name):
        try: res = av.search(q, "STOCK", 10)
        except Exception as e: time.sleep(2); continue
        for h in res.get("hits", []):
            if h.get("type") == "STOCK" and (h.get("title", "").endswith(f"({tick})") or h.get("title", "") == tick) and h.get("flagCode") == "SE":
                hit = h; break
        if hit: break
        time.sleep(0.3)
    if not hit: miss.append(sym); continue
    out.append({"name": name, "id": hit["orderBookId"], "ticker": tick, "yahoo": sym, "segment": "Large Cap" if seg == "L" else "Mid Cap"})
    time.sleep(0.25)
json.dump({"built": time.strftime("%Y-%m-%d"), "source": "kryptosentiment stocks.js + Avanza sök", "stocks": out},
          open("C:/Users/fredrik/android-build/swingedge/app/src/main/assets/stock_universe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(len(out), "hittade; saknas:", miss)
