"""SMA150 daglig vs SMA150 med tredagarsregeln vs köp och behåll på många instrument.
Källor: qa/swing/data (svenska aktier, ETF:er, index) + Yahoo (globala index, råvaror, valutor, räntor, länder-ETF:er,
stora USA-aktier) + cachade kryptor. Hela historiken från 2000-01-01 (eller instrumentets start + 150 dagar).
Kostnad per byte: 0,2 % (0,4 % för kryptor). Kontanter 0 %. Signal på stängning, position nästa handelsdag."""
import json, math, os, sys, time, urllib.request, datetime, glob, statistics, collections
sys.stdout.reconfigure(encoding="utf-8")

SW = "C:/Users/fredrik/android-build/qa/swing/data"
CACHE = "C:/Users/fredrik/android-build/qa/bl/data/many"; os.makedirs(CACHE, exist_ok=True)
CRYPTO = "C:/Users/fredrik/android-build/qa/bl/data/crypto"
YAHOO = {
    "Index": ["^GSPC", "^NDX", "^DJI", "^RUT", "^FTSE", "^GDAXI", "^FCHI", "^N225", "^HSI", "^BVSP", "^GSPTSE", "^AXJO",
              "^KS11", "^BSESN", "^STOXX50E", "^OMX", "^SSMI", "^IBEX", "^AEX", "^MXX", "^TWII", "000001.SS"],
    "Råvaror": ["GC=F", "SI=F", "CL=F", "HG=F", "NG=F", "ZC=F", "ZW=F", "ZS=F", "PL=F", "KC=F", "SB=F", "CT=F"],
    "Valutor": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDSEK=X", "EURSEK=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X"],
    "Räntor/ETF": ["TLT", "IEF", "LQD", "HYG", "GLD", "SLV", "VNQ", "EEM", "EFA", "EWJ", "EWG", "EWU", "EWZ", "EWC", "EWA",
                   "FXI", "EWY", "EWT", "EWW", "EWS", "EWH", "EWL", "EWP", "EWI", "EWQ", "EWD", "XLB", "XLE", "XLF", "XLI",
                   "XLK", "XLP", "XLU", "XLV", "XLY", "SPY", "QQQ", "IWM", "DIA"],
    "USA-aktier": ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "JNJ", "XOM", "WMT", "PG", "KO", "PEP",
                   "INTC", "CSCO", "ORCL", "IBM", "GE", "BA", "CAT", "MMM", "DIS", "MCD", "NKE", "HD", "UNH", "PFE", "MRK",
                   "CVX", "BAC", "C", "WFC", "T", "VZ", "AMD", "QCOM", "TXN", "ADBE", "CRM", "NFLX", "COST", "LLY", "ABT",
                   "MO", "F", "GM", "HON", "UPS", "LMT"],
}

def yahoo(sym):
    p = f"{CACHE}/{sym.replace('^', '_').replace('=', '_')}.json"
    if not os.path.exists(p):
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?period1=946684800&period2={int(time.time())}&interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            j = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
            q = j["indicators"].get("adjclose", [{}])[0].get("adjclose") or j["indicators"]["quote"][0]["close"]
            rows = [(datetime.datetime.fromtimestamp(t, datetime.UTC).strftime("%Y-%m-%d"), c) for t, c in zip(j["timestamp"], q) if c]
        except Exception as e:
            print("Yahoo-fel", sym, e); rows = []
        json.dump(rows, open(p, "w")); time.sleep(0.3)
    return json.load(open(p))

import urllib.parse
U = collections.defaultdict(dict)
for f in glob.glob(f"{SW}/*.ST.json"):
    rows = [(r[0], r[4]) for r in json.load(open(f, encoding="utf-8"))["rows"] if r[4]]
    U["Svenska aktier"][os.path.basename(f)[:-5]] = rows
for cat, syms in YAHOO.items():
    for s in syms: U[cat][s] = yahoo(s)
for f in glob.glob(f"{CRYPTO}/*.json"):
    U["Kryptor"][os.path.basename(f)[:-5]] = json.load(open(f))

def bt(D, C, confirm, cost, n=150, start="2000-01-01"):
    s, eq, pos, streak, peak, dd, tr, rets, d0 = 0.0, 1.0, False, 0, 1.0, 0.0, 0, [], None
    for i, c in enumerate(C):
        live = i > n - 1 and D[i] >= start
        if live:
            d0 = d0 or D[i]
            r = (c / C[i - 1] - 1) if pos else 0.0
            if confirm == 0: r = c / C[i - 1] - 1          # köp och behåll
            eq *= 1 + r; peak = max(peak, eq); dd = min(dd, eq / peak - 1); rets.append(r)
        s += c
        if i >= n: s -= C[i - n]
        if i >= n - 1 and confirm:
            flip = (c < s / n) if pos else (c > s / n)
            streak = streak + 1 if flip else 0
            if streak >= confirm:
                pos = not pos; streak = 0; tr += 1
                if live: eq *= 1 - cost
    if len(rets) < 500: return None
    yrs = (datetime.date.fromisoformat(D[-1]) - datetime.date.fromisoformat(d0)).days / 365.25
    mu = statistics.mean(rets); sd = statistics.pstdev(rets); ppy = len(rets) / yrs
    return {"cagr": eq ** (1 / yrs) - 1 if eq > 0 else -1, "sh": mu / sd * math.sqrt(ppy) if sd else 0, "dd": dd, "tr": tr / yrs, "yrs": yrs}

res = collections.defaultdict(list)
for cat, items in U.items():
    cost = 0.004 if cat == "Kryptor" else 0.002
    for name, rows in items.items():
        rows = [r for r in rows if r[1] and r[1] > 0]
        if len(rows) < 800: continue
        D, C = [r[0] for r in rows], [r[1] for r in rows]
        a, b, h = bt(D, C, 1, cost), bt(D, C, 3, cost), bt(D, C, 0, cost)
        if a and b and h: res[cat].append((name, a, b, h))

med = statistics.median
print(f"{'Kategori':15} {'n':>4} | {'3d>daglig avk':>13} {'3d>daglig Sh':>12} | {'3d>B&H Sh':>9} {'dagl>B&H Sh':>11} | "
      f"{'Sharpe dagl/3d/B&H':>19} | {'maxDD dagl/3d/B&H':>18} | {'aff/år dagl/3d':>14}")
tot = []
for cat, L in res.items():
    tot += L; n = len(L)
    f = lambda cond: f"{sum(cond(x) for x in L) / n * 100:3.0f} %"
    print(f"{cat:15} {n:4} | {f(lambda x: x[2]['cagr'] > x[1]['cagr']):>13} {f(lambda x: x[2]['sh'] > x[1]['sh']):>12} | "
          f"{f(lambda x: x[2]['sh'] > x[3]['sh']):>9} {f(lambda x: x[1]['sh'] > x[3]['sh']):>11} | "
          f"{med(x[1]['sh'] for x in L):5.2f} {med(x[2]['sh'] for x in L):5.2f} {med(x[3]['sh'] for x in L):5.2f}   | "
          f"{med(x[1]['dd'] for x in L)*100:4.0f} {med(x[2]['dd'] for x in L)*100:4.0f} {med(x[3]['dd'] for x in L)*100:4.0f} % | "
          f"{med(x[1]['tr'] for x in L):5.1f} {med(x[2]['tr'] for x in L):5.1f}")
L = tot; n = len(L)
print(f"{'ALLA':15} {n:4} | {sum(x[2]['cagr'] > x[1]['cagr'] for x in L)/n*100:11.0f} % {sum(x[2]['sh'] > x[1]['sh'] for x in L)/n*100:10.0f} % | "
      f"{sum(x[2]['sh'] > x[3]['sh'] for x in L)/n*100:7.0f} % {sum(x[1]['sh'] > x[3]['sh'] for x in L)/n*100:9.0f} % | "
      f"{med(x[1]['sh'] for x in L):5.2f} {med(x[2]['sh'] for x in L):5.2f} {med(x[3]['sh'] for x in L):5.2f}   | "
      f"{med(x[1]['dd'] for x in L)*100:4.0f} {med(x[2]['dd'] for x in L)*100:4.0f} {med(x[3]['dd'] for x in L)*100:4.0f} % | "
      f"{med(x[1]['tr'] for x in L):5.1f} {med(x[2]['tr'] for x in L):5.1f}")
d = [x[2]['sh'] - x[1]['sh'] for x in L]
print(f"Sharpe-skillnad 3d − daglig: median {med(d):+.3f}, medel {statistics.mean(d):+.3f}, ±SE {statistics.stdev(d)/math.sqrt(n):.3f}")
