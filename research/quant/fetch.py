"""Hämtar daglig OHLCV (justerad för utdelning och split) plus utdelnings- och splithändelser från Yahoo Finance.

Cache: config.DATA_DIR/<symbol>.json  ({"symbol", "currency", "rows": [[date, o, h, l, adjclose, volume, close]],
"dividends": [[date, amount]], "splits": [[date, ratio]]}). Befintliga filer hämtas inte om utan --force.
Kör: python -E -m quant.fetch [--force] [--only SYMBOL ...]
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from . import config

UA = {"User-Agent": "SwingEdge-research/2.0 (+https://github.com/Skrooot/swingedge)"}


def path(sym):
    return os.path.join(config.DATA_DIR, re.sub(r"[^A-Za-z0-9._-]", "_", sym) + ".json")


def fetch(sym):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym)
           + "?period1=0&period2=" + str(int(time.time())) + "&interval=1d&events=div%2Csplit")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                res = json.load(r)["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
            off = res["meta"].get("gmtoffset", 0)
            day = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t + off))
            rows = {}
            for i, t in enumerate(res.get("timestamp") or []):
                c, a = q["close"][i], adj[i]
                if c is None or a is None or c <= 0 or a <= 0:
                    continue
                f = a / c
                o, h, l = (q[k][i] or c for k in ("open", "high", "low"))
                rows[day(t)] = [day(t), round(o * f, 6), round(h * f, 6), round(l * f, 6), round(a, 6), q["volume"][i] or 0, round(c, 6)]
            ev = res.get("events", {})
            divs = sorted([day(int(k)), v["amount"]] for k, v in ev.get("dividends", {}).items())
            spl = sorted([day(int(k)), v["numerator"] / v["denominator"]] for k, v in ev.get("splits", {}).items() if v.get("denominator"))
            return {"symbol": sym, "currency": res["meta"].get("currency"), "rows": sorted(rows.values()), "dividends": divs, "splits": spl}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (attempt + 1))
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None


def main(argv):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    from .data import all_symbols
    syms = argv[argv.index("--only") + 1:] if "--only" in argv else all_symbols()
    for s in syms:
        if os.path.exists(path(s)) and "--force" not in argv:
            continue
        d = fetch(s)
        if d and d["rows"]:
            json.dump(d, open(path(s), "w"))
            print(s, d["currency"], len(d["rows"]), d["rows"][0][0], "->", d["rows"][-1][0], flush=True)
        else:
            json.dump({"symbol": s, "currency": None, "rows": [], "dividends": [], "splits": []}, open(path(s), "w"))
            print(s, "SAKNAS", flush=True)
        time.sleep(0.6)


if __name__ == "__main__":
    main(sys.argv[1:])
