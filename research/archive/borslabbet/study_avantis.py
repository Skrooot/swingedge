"""Avantis-ETF:er (Global Equity, Global Small Cap Value, Emerging Markets) mot index och i kombination med SwingEdge.
UCITS-versionerna (AVWC, AVWS, AVEM på Xetra) startade okt 2024–mar 2025, så längre historik byggs med de
amerikanska Avantis-fonderna som proxy från okt 2019. Skriver results_avantis.json."""
import json, sys, math, os, time
sys.stdout.reconfigure(encoding="utf-8")
import gtf
from study_ext import yahoo  # samma hämtning (justerad stängning, månadsslut)
from swingedge_series import load_swingedge

CACHE = "data/avantis.json"
SYMS = ["AVWC.DE", "AVWS.DE", "AVEM.DE", "AVUS", "AVDE", "AVEM", "AVUV", "AVDV", "ACWI", "EEM", "VB", "VSS"]
data = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
for s in SYMS:
    if s not in data: data[s] = yahoo(s); time.sleep(0.4)
json.dump(data, open(CACHE, "w", encoding="utf-8"))
usd = gtf.Y["SEK=X"]; eur = gtf.Y["EURSEK=X"]
R = {s: gtf.rets(gtf.ffill(data[s], eur if s.endswith(".DE") else usd)) for s in SYMS}
def mix(w, ms): return {m: sum(x * R[k][m] for k, x in w.items()) for m in ms}

ms = [m for m in gtf.months("2019-11", gtf.LAST) if all(m in R[s] for s in ["AVUS", "AVDE", "AVEM", "AVUV", "AVDV", "ACWI", "EEM", "VB", "VSS"])]
P = {
    "Global Equity (proxy 62 AVUS/28 AVDE/10 AVEM)": mix({"AVUS": .62, "AVDE": .28, "AVEM": .10}, ms),
    "Global Small Cap Value (proxy 60 AVUV/40 AVDV)": mix({"AVUV": .6, "AVDV": .4}, ms),
    "Emerging Markets (AVEM, USA-noterad)": mix({"AVEM": 1}, ms),
    "Världsindex ACWI": mix({"ACWI": 1}, ms),
    "Tillväxtmarknader EEM": mix({"EEM": 1}, ms),
    "Småbolag marknadsvikt (60 VB/40 VSS)": mix({"VB": .6, "VSS": .4}, ms),
}
P["Avantis tredjedelar"] = {m: sum(P[k][m] for k in list(P)[:3]) / 3 for m in ms}

# proxyns kvalitet: korrelation och avvikelse mot UCITS-fonderna där båda finns
check = {}
for uc, px in (("AVWC.DE", "Global Equity (proxy 62 AVUS/28 AVDE/10 AVEM)"), ("AVWS.DE", "Global Small Cap Value (proxy 60 AVUV/40 AVDV)"), ("AVEM.DE", "Emerging Markets (AVEM, USA-noterad)")):
    mm = [m for m in ms if m in R[uc]][1:]
    x = [R[uc][m] for m in mm]; y = [P[px][m] for m in mm]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    c = sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    check[uc] = {"months": len(mm), "corr": c, "ucits_total": math.prod(1 + v for v in x) - 1, "proxy_total": math.prod(1 + v for v in y) - 1}

SE = load_swingedge()
G = gtf.run(gtf.ASSETS, "2002-08", gtf.LAST); GTF = dict(zip(G["m"], G["r"]))
ms2 = [m for m in ms if all(m in v for v in SE.values()) and m in GTF]
A = P["Avantis tredjedelar"]
C = {k: {m: P[k][m] for m in ms2} for k in P}
C["SwingEdge med guld"] = {m: SE["SwingEdge med guld"][m] for m in ms2}
C["SwingEdge 20/40/40"] = {m: SE["SwingEdge 20/40/40"][m] for m in ms2}
C["Global trendföljning"] = {m: GTF[m] for m in ms2}
C["50 % Avantis + 50 % SwingEdge med guld"] = {m: .5 * A[m] + .5 * SE["SwingEdge med guld"][m] for m in ms2}
C["80 % Avantis + 20 % Bitcoin Trend"] = {m: .8 * A[m] + .2 * SE["Bitcoin Trend (hink)"][m] for m in ms2}
C["50 % Avantis + 50 % Global trendföljning"] = {m: .5 * A[m] + .5 * GTF[m] for m in ms2}
C["60 % Avantis + 20 % Bitcoin Trend + 20 % Global trendföljning"] = {m: .6 * A[m] + .2 * SE["Bitcoin Trend (hink)"][m] + .2 * GTF[m] for m in ms2}

res = {"period": [ms2[0], ms2[-1]], "proxy_check": check, "metrics": {}, "corr": {}}
for n, r in C.items():
    x = gtf.metrics({"m": ms2, "r": [r[m] for m in ms2], "w": [], "turn": 0.0, "pos": []})
    res["metrics"][n] = x
    print(f"{n[:62]:62} CAGR {x['cagr']*100:5.1f} vol {x['vol']*100:5.1f} Sharpe {x['sharpe']:.2f} MDD {x['maxdd']*100:4.0f}")
def corr(a, b):
    x = [a[m] for m in ms2]; y = [b[m] for m in ms2]; mx, my = sum(x) / len(x), sum(y) / len(y)
    return sum((p - mx) * (q - my) for p, q in zip(x, y)) / math.sqrt(sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y))
for a in list(P)[:3] + ["Avantis tredjedelar"]:
    for b in ("Världsindex ACWI", "SwingEdge med guld", "Global trendföljning"):
        res["corr"][f"{a} | {b}"] = corr(C[a], C[b])
for k in ("Bitcoin Trend (hink)", "S&P 500 Trend (hink)", "Lika vikt (hink)"):
    res["corr"][f"Avantis tredjedelar | {k}"] = corr(C["Avantis tredjedelar"], {m: SE[k][m] for m in ms2})
json.dump(res, open("results_avantis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(check, ensure_ascii=False)); print(json.dumps(res["corr"], ensure_ascii=False, indent=0))
print("period", res["period"])
