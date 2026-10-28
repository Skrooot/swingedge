"""SwingEdge med guld: lönar det sig att lägga till fler trendhinkar? Daglig portföljsimulering i SEK.
Produkter (Yahoo, justerade kurser, omräknade med USDSEK): XBT = BTC-USD, SXR8 = SPY, XACT = XACT-OMXS30.ST,
guld = GLD, Nasdaq = QQQ, EM = EEM, ETH = ETH-USD. Regler:
  Bitcoin/Ethereum Trend: SMA150 på dagsstängning i USD, daglig eller tredagarsregel, position nästa dag.
  S&P 500 / Nasdaq / EM Trend: SMA200 på månadens sista handelsdag (indexets egen serie), gäller nästa månad.
  Lika vikt: XACT, SXR8, XBT, guld 10 % var.
Hinkarna och lika vikt-delen ombalanseras till målvikt efter varje månadsskifte. Kostnad: trendbyte 0,4 % (krypto)
/ 0,2 % (ETF) av hinkens värde, ombalansering 0,2 % av omsatt belopp. Kontanter 0 %."""
import json, math, os, sys, time, urllib.request, urllib.parse, datetime, statistics
sys.stdout.reconfigure(encoding="utf-8")
CACHE = "C:/Users/fredrik/android-build/qa/bl/data/many"; os.makedirs(CACHE, exist_ok=True)

def yahoo(sym):
    p = f"{CACHE}/{sym.replace('^', '_').replace('=', '_')}.json"
    if not os.path.exists(p) or os.path.getsize(p) < 10:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?period1=946684800&period2={int(time.time())}&interval=1d"
        j = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60))["chart"]["result"][0]
        q = j["indicators"].get("adjclose", [{}])[0].get("adjclose") or j["indicators"]["quote"][0]["close"]
        rows = [(datetime.datetime.fromtimestamp(t, datetime.UTC).strftime("%Y-%m-%d"), c) for t, c in zip(j["timestamp"], q) if c]
        json.dump(rows, open(p, "w"))
    return dict(json.load(open(p)))

RAW = {k: yahoo(s) for k, s in {"BTC": "BTC-USD", "ETH": "ETH-USD", "SPY": "SPY", "QQQ": "QQQ", "EEM": "EEM",
                                "GLD": "GLD", "XACT": "XACT-OMXS30.ST", "FX": "USDSEK=X"}.items()}
DAYS = sorted(d for d in RAW["BTC"] if d >= "2014-09-17")
def ffill(series):
    out, last = {}, None
    for d in DAYS:
        last = series.get(d, last); out[d] = last
    return out
P = {k: ffill(v) for k, v in RAW.items()}
SEK = {k: {d: (P[k][d] * P["FX"][d] if k != "XACT" else P[k][d]) if P[k][d] and P["FX"][d] else None for d in DAYS}
       for k in ("BTC", "ETH", "SPY", "QQQ", "EEM", "GLD", "XACT")}

def daily_trend(sym, confirm):
    """Tillstånd per dag (beslut efter dagens stängning), SMA150 i USD."""
    st, s, q, on, streak = {}, 0.0, [], False, 0
    for d in DAYS:
        c = RAW[sym].get(d)
        if c:
            q.append(c); s += c
            if len(q) > 150: s -= q.pop(0)
            if len(q) == 150:
                flip = (c < s / 150) if on else (c > s / 150)
                streak = streak + 1 if flip else 0
                if streak >= confirm: on = not on; streak = 0
        st[d] = on if len(q) == 150 else None
    return st

def monthly_trend(sym):
    """SMA200 på månadens sista handelsdag i instrumentets egen serie; gäller från nästa handelsdag."""
    ds = sorted(RAW[sym]); cs = [RAW[sym][d] for d in ds]; dec = {}
    for i in range(199, len(ds)):
        if i + 1 < len(ds) and ds[i + 1][:7] != ds[i][:7]:
            dec[ds[i][:7]] = cs[i] > sum(cs[i - 199:i + 1]) / 200
    st, cur = {}, None
    for d in DAYS:
        m = (datetime.date.fromisoformat(d[:7] + "-01") - datetime.timedelta(days=1)).strftime("%Y-%m")
        st[d] = dec.get(m)
    return st

def run(sleeves, start, end="2099"):
    """sleeves: lista av (vikt, typ, produkt, signal-dict|None). typ 'trend' eller 'ew' (signal None)."""
    days = [d for d in DAYS if start <= d <= end]
    val = [w for w, *_ in sleeves]; eq = 1.0; rets = []; switches = 0; peak = 1.0; dd = 0.0
    held = [None] * len(sleeves)
    for i in range(1, len(days)):
        d0, d1 = days[i - 1], days[i]
        if d1[:7] != d0[:7]:                                    # ombalansering vid månadsskifte
            tot = sum(val); turn = sum(abs(v - w * tot) for v, (w, *_) in zip(val, sleeves)) / 2
            val = [w * tot for w, *_ in sleeves]; val = [v * (1 - 0.002 * turn / tot) for v in val]
        new = []
        for j, (w, kind, prod, sig) in enumerate(sleeves):
            s = sig[d0] if sig else True                        # gårdagens beslut gäller i dag
            if s is None: raise SystemExit(f"signal saknas {prod} {d0}")
            if held[j] is not None and s != held[j]:
                val[j] *= 1 - (0.004 if prod in ("BTC", "ETH") else 0.002); switches += 1
            held[j] = s
            r = SEK[prod][d1] / SEK[prod][d0] - 1 if s else 0.0
            new.append(val[j] * (1 + r))
        tot0 = sum(val); val = new; r = sum(val) / tot0 - 1
        eq *= 1 + r; rets.append(r); peak = max(peak, eq); dd = min(dd, eq / peak - 1)
    yrs = (datetime.date.fromisoformat(days[-1]) - datetime.date.fromisoformat(days[0])).days / 365.25
    sd = statistics.pstdev(rets)
    return {"cagr": eq ** (1 / yrs) - 1, "sh": statistics.mean(rets) / sd * math.sqrt(365) if sd else 0, "dd": dd, "sw": switches / yrs}

BTC1, BTC3, ETH3 = daily_trend("BTC", 1), daily_trend("BTC", 3), daily_trend("ETH", 3)
SPT, NDT, EMT = monthly_trend("SPY"), monthly_trend("QQQ"), monthly_trend("EEM")
EW = lambda w: [(w / 4, "ew", p, None) for p in ("XACT", "SPY", "BTC", "GLD")]
V = {
    "1 Appen i dag (BTC daglig)":            [(0.2, "t", "BTC", BTC1)] + EW(0.4) + [(0.4, "t", "SPY", SPT)],
    "2 BTC med tredagarsregel":              [(0.2, "t", "BTC", BTC3)] + EW(0.4) + [(0.4, "t", "SPY", SPT)],
    "3 = 2 + Nasdaq-trend (S&P 20 / NDX 20)": [(0.2, "t", "BTC", BTC3)] + EW(0.4) + [(0.2, "t", "SPY", SPT), (0.2, "t", "QQQ", NDT)],
    "4 = 2 + EM-trend (S&P 30 / EM 10)":      [(0.2, "t", "BTC", BTC3)] + EW(0.4) + [(0.3, "t", "SPY", SPT), (0.1, "t", "EEM", EMT)],
    "5 = 2 + ETH-trend (BTC 10 / ETH 10)":    [(0.1, "t", "BTC", BTC3), (0.1, "t", "ETH", ETH3)] + EW(0.4) + [(0.4, "t", "SPY", SPT)],
    "6 = 2 + allt ovan":                      [(0.1, "t", "BTC", BTC3), (0.1, "t", "ETH", ETH3)] + EW(0.4) + [(0.2, "t", "SPY", SPT), (0.1, "t", "QQQ", NDT), (0.1, "t", "EEM", EMT)],
}
W = [("2015-06-01", "2026-09-30", "2015-06 – 2026-09"), ("2018-07-01", "2026-09-30", "2018-07 – 2026-09"), ("2020-01-01", "2026-09-30", "2020-01 – 2026-09")]
print("Avkastning/år, Sharpe, största fall, trendbyten/år")
for a, b, lab in W:
    print(f"\n{lab}")
    for k, sl in V.items():
        if "ETH" in k or "allt" in k:
            if a < "2018-07-01": continue
        r = run(sl, a, b)
        print(f"  {k:40} {r['cagr']*100:5.1f} %  {r['sh']:.2f}  {r['dd']*100:4.0f} %  {r['sw']:4.1f}")
