"""Andra trendregler för Bitcoin-delen, samma robusthetsprov som study_btc_robust.py: rutnät av inställningar,
fyra delperioder och ETH-USD som inte användes vid valet. Position i [0, 1]; kostnad 0,40 % på varje förändring
(omsättning), så delpositioner kostar i proportion. Signal på stängning, position nästa dag, kontanter 0 %."""
import json, math, sys, statistics
sys.stdout.reconfigure(encoding="utf-8")

def load(sym):
    rows = [(r[0], r[4]) for r in json.load(open(f"C:/Users/fredrik/android-build/qa/swing/data/{sym}.json", encoding="utf-8"))["rows"] if r[4]]
    return [d for d, _ in rows], [c for _, c in rows]

COST = 0.004

def sma(C, n):
    out, s = [None] * len(C), 0.0
    for i, c in enumerate(C):
        s += c
        if i >= n: s -= C[i - n]
        if i >= n - 1: out[i] = s / n
    return out

def ema(C, n):
    out, e, k = [None] * len(C), None, 2 / (n + 1)
    for i, c in enumerate(C):
        e = c if e is None else e + k * (c - e)
        if i >= n - 1: out[i] = e
    return out

def above(C, m): return [0.0 if m[i] is None else float(C[i] > m[i]) for i in range(len(C))]
def r_sma(C, n): return above(C, sma(C, n))
def r_ema(C, n): return above(C, ema(C, n))
def r_cross(C, f, s):
    a, b = sma(C, f), sma(C, s); return [0.0 if b[i] is None else float(a[i] > b[i]) for i in range(len(C))]
def r_donchian(C, n):
    out, on = [], 0.0; x = n // 2
    for i in range(len(C)):
        if i < n: out.append(0.0); continue
        if C[i] >= max(C[i - n:i]): on = 1.0
        elif C[i] <= min(C[i - x:i]): on = 0.0
        out.append(on)
    return out
def r_mom(C, L): return [0.0 if i < L else float(C[i] > C[i - L]) for i in range(len(C))]
def r_ens(C, ns):
    ms = [sma(C, n) for n in ns]
    return [0.0 if ms[-1][i] is None else sum(C[i] > m[i] for m in ms) / len(ns) for i in range(len(C))]
def r_voltgt(C, n, tgt, step=0.1):
    base, out, w = r_sma(C, n), [], 0.0
    for i in range(len(C)):
        if i < 31 or base[i] == 0: w = 0.0; out.append(0.0); continue
        rs = [math.log(C[j] / C[j - 1]) for j in range(i - 29, i + 1)]
        vol = statistics.pstdev(rs) * math.sqrt(365)
        want = min(1.0, tgt / vol) if vol > 0 else 1.0
        if abs(want - w) > step or w == 0: w = want
        out.append(w)
    return out

def run(D, C, st, a, b):
    eq, peak, dd, rets, turn, was = 1.0, 1.0, 0.0, [], 0.0, None
    for i in range(1, len(C)):
        if not (a <= D[i] <= b): continue
        pos = st[i - 1]; r = pos * (C[i] / C[i - 1] - 1)
        if was is not None: r -= abs(pos - was) * COST; turn += abs(pos - was)
        was = pos; eq *= 1 + r; peak = max(peak, eq); dd = min(dd, eq / peak - 1); rets.append(r)
    n = len(rets); mu = sum(rets) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in rets) / (n - 1))
    return {"cagr": eq ** (365.25 / n) - 1, "sh": mu / sd * math.sqrt(365), "dd": dd, "turn": turn / (n / 365.25)}

FAM = {
    "Daglig SMA (appen)":            [lambda C, n=n: r_sma(C, n) for n in (100, 125, 150, 175, 200)],
    "EMA":                           [lambda C, n=n: r_ema(C, n) for n in (100, 125, 150, 175, 200)],
    "Korsning snabb/långsam SMA":    [lambda C, f=f, s=s: r_cross(C, f, s) for f, s in ((20, 100), (30, 150), (50, 150), (50, 200), (20, 200))],
    "Donchian-utbrott":              [lambda C, n=n: r_donchian(C, n) for n in (20, 50, 100, 150, 200)],
    "Momentum (pris > pris för L d)":[lambda C, L=L: r_mom(C, L) for L in (60, 90, 120, 180, 250, 365)],
    "Ensemble av flera SMA":         [lambda C, ns=ns: r_ens(C, ns) for ns in ((50, 100, 150, 200, 250), (100, 150, 200), (50, 100, 200), (75, 125, 175, 225), (20, 50, 100, 150, 200))],
    "SMA + volatilitetsstyrning":    [lambda C, n=n, t=t: r_voltgt(C, n, t) for n in (100, 150, 200) for t in (0.4, 0.6, 0.8)],
}
SUB = [("2015-06-01", "2017-12-31"), ("2018-01-01", "2020-12-31"), ("2021-01-01", "2023-12-31"), ("2024-01-01", "2026-12-31")]
data = {"BTC": load("BTC-USD"), "ETH": load("ETH-USD")}
START = {"BTC": "2015-06-01", "ETH": "2017-11-09"}
bh = {k: run(D, C, [1.0] * len(C), START[k], D[-1]) for k, (D, C) in data.items()}
print(f"köp och behåll: BTC Sh {bh['BTC']['sh']:.2f} {bh['BTC']['cagr']*100:.0f} %/år maxDD {bh['BTC']['dd']*100:.0f} % | ETH Sh {bh['ETH']['sh']:.2f}\n")
total = 0
for fam, fs in FAM.items():
    rb, eth, subw, dd, cg, tu = [], [], [], [], [], []
    for f in fs:
        D, C = data["BTC"]; st = f(C); r = run(D, C, st, START["BTC"], D[-1])
        rb.append(r["sh"]); dd.append(r["dd"]); cg.append(r["cagr"]); tu.append(r["turn"])
        subw.append(min(run(D, C, st, a, b)["sh"] for a, b in SUB))
        D, C = data["ETH"]; eth.append(run(D, C, f(C), START["ETH"], D[-1])["sh"])
    total += len(fs)
    print(f"{fam:31} BTC Sh {statistics.median(rb):.2f}/{min(rb):.2f}  {statistics.median(cg)*100:4.0f} %/år  maxDD {statistics.median(dd)*100:4.0f} %  "
          f"sämsta delper. {min(subw):5.2f}  omsättn./år {statistics.median(tu):4.1f}  | ETH Sh {statistics.median(eth):.2f}/{min(eth):.2f}  (n={len(fs)})")
print(f"\n{total} inställningar provade totalt")
