"""NR7Trend-Krypto (HK Strategitest, veckor, alla år, lista Kryptovalutor, export nr7krypto_trades.csv)
jämfört med daglig SMA150 och köp och behåll på samma USD-kryptor. Dagskurser från Yahoo (cache i data/crypto/).
Fönster per kryptovaluta: från dag 150 i Yahoo-serien till sista dagen. NR7: affärer vars köpdag ligger i fönstret,
avkastning = HK:s Win(%) (redan minus courtage), sammansatt. SMA150: signal på stängning, position nästa dag,
0,40 % per sida. Uppenbara datafel i HK-exporten (enskild affär > +1000 %) redovisas separat."""
import csv, json, math, os, sys, time, urllib.request, datetime, collections
sys.stdout.reconfigure(encoding="utf-8")

YH = {"ADA": "ADA-USD", "ARB": "ARB11841-USD", "AVAX": "AVAX-USD", "BCH": "BCH-USD", "BNB": "BNB-USD", "BTC": "BTC-USD",
      "DOGE": "DOGE-USD", "DOT": "DOT-USD", "ETC": "ETC-USD", "ETH": "ETH-USD", "FET": "FET-USD", "HBAR": "HBAR-USD",
      "ICP": "ICP-USD", "LINK": "LINK-USD", "LTC": "LTC-USD", "NEAR": "NEAR-USD", "SOL": "SOL-USD", "SUI": "SUI20947-USD",
      "TRX": "TRX-USD", "UNI": "UNI7083-USD", "XLM": "XLM-USD", "XRP": "XRP-USD"}
CACHE = "C:/Users/fredrik/android-build/qa/bl/data/crypto"; os.makedirs(CACHE, exist_ok=True)

def yahoo(sym):
    p = f"{CACHE}/{sym}.json"
    if not os.path.exists(p):
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?period1=1262304000&period2={int(time.time())}&interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        j = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
        rows = [(datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), c) for t, c in zip(j["timestamp"], j["indicators"]["quote"][0]["close"]) if c]
        json.dump(rows, open(p, "w")); time.sleep(0.5)
    return json.load(open(p))

def sma_bt(C, n=150, cost=0.004):
    s, eq, was, pos = 0.0, 1.0, False, False
    peak, dd = 1.0, 0.0; trades = 0
    for i, c in enumerate(C):
        if i > n - 1:
            r = (c / C[i - 1] - 1) if pos else 0.0
            eq *= 1 + r
            peak = max(peak, eq); dd = min(dd, eq / peak - 1)
        s += c
        if i >= n: s -= C[i - n]
        if i >= n - 1:
            new = c > s / n
            if new != pos: eq *= 1 - cost; trades += 1
            pos = new
    return eq - 1, dd, trades

rows = [x for x in csv.reader(open("C:/Users/fredrik/Documents/nr7krypto_trades.csv", encoding="latin1"), delimiter=";") if x and x[0].isdigit()]
nr7 = collections.defaultdict(list)
for x in rows:
    k = x[2].split("/")[0].strip()
    if k in YH:
        exit_d = datetime.date(int(x[0][:4]), int(x[0][4:6]), int(x[0][6:]))
        nr7[k].append((exit_d - datetime.timedelta(weeks=int(x[3])), float(x[7].replace(",", ".").replace("+", ""))))

print(f"{'Krypto':6} {'från':10} {'år':>4} | {'NR7 n':>5} {'NR7 tot':>9} | {'SMA150 tot':>10} {'maxDD':>6} {'aff':>4} | {'B&H tot':>9}  {'not'}")
agg = []
for k, sym in YH.items():
    try: D, C = zip(*yahoo(sym))
    except Exception as e: print(k, "Yahoo-fel", e); continue
    start = datetime.date.fromisoformat(D[150]); yrs = (len(D) - 150) / 365.25
    tr = [w for d, w in nr7.get(k, []) if d >= start]
    bad = [w for w in tr if w > 1000]; ok = [w for w in tr if w <= 1000]
    e = 1.0
    for w in ok: e *= 1 + w / 100
    s, dd, n = sma_bt(list(C)); bh = C[-1] / C[150] - 1
    agg.append((k, e - 1, s, bh, yrs, len(ok)))
    print(f"{k:6} {start} {yrs:4.1f} | {len(ok):5} {(e-1)*100:8.0f}% | {s*100:9.0f}% {dd*100:5.0f}% {n:4} | {bh*100:8.0f}%  {'datafel bortrensat: ' + ', '.join(f'+{w:.0f} %' for w in bad) if bad else ''}")

def ann(x, y): return (1 + x) ** (1 / y) - 1 if x > -1 else -1
print("\nPer år (median över kryptor):",
      "NR7", f"{sorted(ann(a[1], a[4]) for a in agg)[len(agg)//2]*100:.0f} %",
      "| SMA150", f"{sorted(ann(a[2], a[4]) for a in agg)[len(agg)//2]*100:.0f} %",
      "| B&H", f"{sorted(ann(a[3], a[4]) for a in agg)[len(agg)//2]*100:.0f} %")
print("NR7 bättre än SMA150 på", sum(a[1] > a[2] for a in agg), "av", len(agg), "| SMA150 bättre än B&H på", sum(a[2] > a[3] for a in agg), "av", len(agg),
      "| NR7 bättre än B&H på", sum(a[1] > a[3] for a in agg), "av", len(agg))
