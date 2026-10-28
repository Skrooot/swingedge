"""Val av en enda strategi: jämför kandidaterna och validerar Kryptotrend SMA150 (BTC + ETH) på Avanza-produkterna.
Signal: dagsstängning BTC-USD/ETH-USD > SMA150 (stapeln klar 00:00 UTC), affär på produktens stängning första
handelsdagen därefter (samma regel som appens backtest). Kostnad 0,40 % per sida. Skriver results_winner.json."""
import json, math, random, sys
from datetime import date, timedelta
sys.stdout.reconfigure(encoding="utf-8")
SW = "C:/Users/fredrik/android-build/qa/swing/data/"; ED = "C:/Users/fredrik/android-build/qa/edge/data/"
def rows(p): return [(r[0], r[4]) for r in json.load(open(p, encoding="utf-8"))["rows"] if r[4]]
U = {"BTC": rows(SW + "BTC-USD.json"), "ETH": rows(ED + "ETH-USD.json")}
P = {"BTC": rows(SW + "BITCOIN-XBT.ST.json"), "ETH": rows(SW + "ETHEREUM-XBT.ST.json")}
COST = 0.004

def states(u, n):
    d = [x for x, _ in u]; c = [y for _, y in u]; out = {}; s = sum(c[:n - 1])
    for i in range(n - 1, len(c)):
        s += c[i]
        if i >= n: s -= c[i - n]
        out[d[i]] = c[i] > s / n
    return out

def weights(asset, n=150, delay=0):
    """w per produktdag: läget som är känt före nästa produktdags öppning (+delay dagar)."""
    st = states(U[asset], n); ud = sorted(st); pd = [d for d, _ in P[asset]]
    w, k, cur = {}, 0, None
    for i, d in enumerate(pd):
        # delay > 0 = äldre information (läget känt före produktdag i+1-delay), aldrig nyare
        j = i + 1 - delay
        nxt = pd[j] if 0 <= j < len(pd) else (date.fromisoformat(d) + timedelta(days=1 - delay)).isoformat()
        while k < len(ud) and ud[k] < nxt: cur = st[ud[k]]; k += 1
        w[d] = None if cur is None else (1.0 if cur else 0.0)
    return w

def daily(asset, w, cost=COST):
    """Dagsavkastning för en hink (handel på stängning dag t enligt w[t-1]) och lista över affärer."""
    pd = [d for d, _ in P[asset]]; pc = [c for _, c in P[asset]]
    r = {}; pos = 0.0; trades = []; entry = None
    for t in range(1, len(pd)):
        eq = 1 + pos * (pc[t] / pc[t - 1] - 1)
        tgt = w.get(pd[t - 1]) or 0.0
        if abs(tgt - pos) > 1e-9:
            eq *= 1 - abs(tgt - pos) * cost
            if tgt > 0: entry = (pd[t], pc[t])
            elif entry: trades.append((entry[0], pd[t], pc[t] / entry[1] * (1 - cost) ** 2 - 1)); entry = None
            pos = tgt
        r[pd[t]] = eq - 1
    if entry: trades.append((entry[0], None, pc[-1] / entry[1] * (1 - cost) ** 2 - 1))
    return r, trades

def portfolio(parts, days):
    """Lika vikt mellan hinkarna, ombalansering vid varje månadsskifte (inga kostnader för den interna vikten)."""
    w = {k: 1 / len(parts) for k in parts}; out = {}
    for i, d in enumerate(days):
        g = sum(w[k] * parts[k].get(d, 0.0) for k in parts)
        out[d] = g
        w = {k: w[k] * (1 + parts[k].get(d, 0.0)) / (1 + g) for k in parts}
        if i + 1 < len(days) and days[i + 1][:7] != d[:7]: w = {k: 1 / len(parts) for k in parts}
    return out

def metrics(r, days):
    x = [r[d] for d in days]; eq = peak = 1.0; mdd = 0.0
    for v in x: eq *= 1 + v; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    yrs = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days / 365.25
    mu = sum(x) / len(x); sd = math.sqrt(sum((v - mu) ** 2 for v in x) / (len(x) - 1))
    return {"from": days[0], "to": days[-1], "cagr": eq ** (1 / yrs) - 1, "sharpe": mu / sd * math.sqrt(252), "maxdd": mdd, "vol": sd * math.sqrt(252)}

def boot(a, b, days, n=2000, block=21, seed=3):
    rnd = random.Random(seed); T = len(days); worse = 0
    xa = [a[d] for d in days]; xb = [b[d] for d in days]
    def sh(x): mu = sum(x) / len(x); sd = math.sqrt(sum((v - mu) ** 2 for v in x) / (len(x) - 1)); return mu / sd
    for _ in range(n):
        idx = []
        while len(idx) < T:
            s = rnd.randrange(T); idx += [(s + j) % T for j in range(max(1, int(rnd.expovariate(1 / block))))]
        idx = idx[:T]
        worse += sh([xa[i] for i in idx]) - sh([xb[i] for i in idx]) <= 0
    return worse / n

def cagr_diff(a, b, days):
    return metrics(a, days)["cagr"] - metrics(b, days)["cagr"]

res = {}
days = sorted(set(d for d, _ in P["BTC"]) & set(d for d, _ in P["ETH"]))
S = {}; TR = {}
for a in ("BTC", "ETH"):
    S[a], TR[a] = daily(a, weights(a))
    S[a + "_bh"], _ = daily(a, {d: 1.0 for d, _ in P[a]})
start = next(d for d in days if weights("ETH").get(d) is not None and weights("BTC").get(d) is not None)
days = [d for d in days if d > start]
K = portfolio({"BTC": S["BTC"], "ETH": S["ETH"]}, days)
KBH = portfolio({"BTC": S["BTC_bh"], "ETH": S["ETH_bh"]}, days)
cands = {"Kryptotrend SMA150 (BTC + ETH)": K, "Bitcoin Trend SMA150 ensam": S["BTC"], "Ether Trend SMA150 ensam": S["ETH"],
         "Köp och behåll BTC + ETH": KBH, "Köp och behåll Bitcoin Tracker One": S["BTC_bh"]}
TEST = "2020-01-01"; td = [d for d in days if d >= TEST]
SUB = [("2018-05-01", "2020-12-31"), ("2021-01-01", "2023-12-31"), ("2024-01-01", "2026-12-31")]
res["period"] = [days[0], days[-1]]; res["test_from"] = TEST
res["candidates"] = {n: {"full": metrics(r, days), "test": metrics(r, td), "sub": [metrics(r, [d for d in days if a <= d <= b]) for a, b in SUB]} for n, r in cands.items()}
res["p_not_better_sharpe_vs_bh"] = {"full": boot(K, KBH, days), "test": boot(K, KBH, td)}
# robusthet: parametrar, fördröjning, kostnad
var = {}
for n_ in (100, 125, 175, 200):
    var[f"SMA{n_}"] = portfolio({a: daily(a, weights(a, n_))[0] for a in ("BTC", "ETH")}, days)
var["En dags extra fördröjning"] = portfolio({a: daily(a, weights(a, delay=1))[0] for a in ("BTC", "ETH")}, days)
var["Kostnad 0,8 % per sida"] = portfolio({a: daily(a, weights(a), 0.008)[0] for a in ("BTC", "ETH")}, days)
res["variants"] = {k: {"full": metrics(v, days), "test": metrics(v, td)} for k, v in var.items()}
# beroende av enstaka affärer: ta bort de tre bästa affärerna per tillgång (sätt deras dagar till kontanter)
def without_best(a, k=3):
    best = sorted(TR[a], key=lambda t: -t[2])[:k]; r = dict(S[a])
    for e, x, _ in best:
        for d in r:
            if d >= e and (x is None or d <= x): r[d] = 0.0
    return r, [(e, x, round(g, 3)) for e, x, g in best]
wb = {a: without_best(a) for a in ("BTC", "ETH")}
res["without_top3"] = {"metrics": metrics(portfolio({a: wb[a][0] for a in wb}, days), days), "removed": {a: wb[a][1] for a in wb},
                       "bh_metrics": metrics(KBH, days)}
res["trades"] = {a: {"n": len(TR[a]), "winrate": sum(1 for t in TR[a] if t[2] > 0) / len(TR[a]),
                     "avg_days": sum((date.fromisoformat(x) - date.fromisoformat(e)).days for e, x, _ in TR[a] if x) / max(1, sum(1 for t in TR[a] if t[1])),
                     "per_year": len(TR[a]) / ((date.fromisoformat(P[a][-1][0]) - date.fromisoformat(P[a][0][0])).days / 365.25)} for a in TR}
json.dump(res, open("results_winner.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def f(m): return f"{m['cagr']*100:6.1f} % {m['sharpe']:.2f} {m['maxdd']*100:4.0f} %"
print("period", res["period"], "| test från", TEST)
for n, v in res["candidates"].items():
    print(f"{n:36} hela {f(v['full'])} | test {f(v['test'])} | " + " | ".join(f(s) for s in v["sub"]))
print("p (Sharpe inte bättre än köp och behåll)", res["p_not_better_sharpe_vs_bh"])
for k, v in res["variants"].items(): print(f"{k:28} hela {f(v['full'])} | test {f(v['test'])}")
print("utan tre bästa affärerna", f(res["without_top3"]["metrics"]), res["without_top3"]["removed"])
print(res["trades"])
# samma test-fönster som SwingEdge-portföljen (månadsdata): jämförelse på identiska månader
import swingedge_series as SS
SE = SS.load_swingedge()
def monthly(r):
    m = {}
    for d in sorted(r): m[d[:7]] = m.get(d[:7], 1.0) * (1 + r[d])
    return {k: v - 1 for k, v in m.items()}
import gtf
KM, BHM = monthly(K), monthly(KBH)
G = gtf.run(gtf.ASSETS, "2002-08", gtf.LAST); GT = dict(zip(G["m"], G["r"]))
for lab, a0 in (("2018-06–", "2018-06"), ("test 2020–", "2020-01")):
    mm = [m for m in sorted(KM) if a0 <= m <= gtf.LAST and m in SE["SwingEdge med guld"] and m in GT]
    for n, r in (("Kryptotrend", KM), ("Köp och behåll BTC+ETH", BHM), ("SwingEdge med guld", SE["SwingEdge med guld"]), ("SwingEdge 20/40/40", SE["SwingEdge 20/40/40"]), ("Global trendföljning", GT)):
        x = gtf.metrics({"m": mm, "r": [r[m] for m in mm], "w": [], "turn": 0.0, "pos": []})
        print(f"{lab:12} {n:24} CAGR {x['cagr']*100:5.1f} Sharpe {x['sharpe']:.2f} MDD {x['maxdd']*100:4.0f} ({mm[0]}–{mm[-1]})")
