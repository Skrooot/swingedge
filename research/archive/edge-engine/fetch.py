"""Hämtar daglig historik (OHLC, justerad för utdelning och split) från Yahoo Finance till data/<symbol>.json.

Användning: python fetch.py [--stocks]   (--stocks hämtar även Large/Mid Cap-listan från appens stocks.js)
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "Kryptosentiment-research/1.0 (+https://github.com/Skrooot/kryptosentiment)"}
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")  # kursdata, inte incheckad

RESEARCH = ["^GSPC", "^NDX", "^OMX", "^STOXX", "GC=F", "BTC-USD", "ETH-USD", "USDSEK=X", "EURSEK=X", "^VIX",
            "XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLY", "XLU", "XLB"]
PRODUCTS = ["XACT-OMXS30.ST", "SXR8.DE", "SXRV.DE", "EXSA.DE", "4GLD.DE", "BITCOIN-XBT.ST", "ETHEREUM-XBT.ST"]
STOCKS_JS = "C:/Users/fredrik/android-build/kryptosentiment/www/stocks.js"


def fname(sym):
    return os.path.join(DATA, re.sub(r"[^A-Za-z0-9._-]", "_", sym) + ".json")


def fetch(sym):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym)
           + "?period1=0&period2=" + str(int(time.time())) + "&interval=1d&events=div%2Csplit")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                d = json.load(r)
            res = d["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
            rows = []
            for i, t in enumerate(res.get("timestamp") or []):
                c, a = q["close"][i], adj[i]
                if c is None or a is None or c <= 0:
                    continue
                f = a / c
                o, h, l = q["open"][i], q["high"][i], q["low"][i]
                rows.append([time.strftime("%Y-%m-%d", time.gmtime(t + res["meta"].get("gmtoffset", 0))),
                             round((o or c) * f, 6), round((h or c) * f, 6), round((l or c) * f, 6), round(a, 6),
                             q["volume"][i] or 0])
            # en rad per datum (Yahoo kan ge dubbletter för dagens bar)
            seen = {}
            for row in rows:
                seen[row[0]] = row
            return {"symbol": sym, "currency": res["meta"].get("currency"), "rows": sorted(seen.values())}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (attempt + 1))
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None


def main():
    os.makedirs(DATA, exist_ok=True)
    syms = RESEARCH + PRODUCTS
    if "--stocks" in sys.argv:
        src = open(STOCKS_JS, encoding="utf-8").read()
        syms += re.findall(r'\["([A-Z0-9-]+\.ST)"', src)
    for s in syms:
        if os.path.exists(fname(s)) and "--force" not in sys.argv:
            continue
        d = fetch(s)
        if d and d["rows"]:
            json.dump(d, open(fname(s), "w"))
            print(s, d["currency"], len(d["rows"]), d["rows"][0][0], "->", d["rows"][-1][0], flush=True)
        else:
            print(s, "MISSING", flush=True)
        time.sleep(0.7)


if __name__ == "__main__":
    main()
