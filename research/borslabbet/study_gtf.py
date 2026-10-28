"""Replikering och validering av Global trendföljning. Skriver results_gtf.json."""
import json, itertools, math, sys
sys.stdout.reconfigure(encoding="utf-8")
import gtf
from gtf import ASSETS, WORLD, SHORT, run, fixed, series_bh, metrics, bootstrap_diff, dsr, pbo, months

START, END = "2002-08", gtf.LAST          # alla nio tillgångar har 12 månaders historik
TRAIN_END, TEST_START = "2013-12", "2014-01"
A = dict(ASSETS); A["Världen"] = WORLD
SUB = [("2002-08", "2009-12"), ("2010-01", "2017-12"), ("2018-01", END)]
res = {"period": [START, END], "assets": {}, "strategies": {}, "notes": []}

for a, sid in [("Sverige", "SEB Sverigefond A → LF Sverige Index (2008-12)"), ("Europa", "Skandia Europa Exponering"),
               ("USA", "Storebrand USA A SEK"), ("Japan", "Skandia Japan Exponering"),
               ("Tillväxtmarknader", "Handelsbanken Tillväxtmarknad A1 → LF Tillväxtmarknad Index A (2014-07)"),
               ("Svenska småbolag", "Swedbank Robur Småbolagsfond Sverige A → PLUS Småbolag Sverige Index (2017-10)"),
               ("Svenska obligationer", "Carnegie Obligationsfond A"), ("Svenska korta räntor", "Handelsbanken Kortränta Defensiv A1"),
               ("Guld", "GC=F i SEK → Xetra-Gold 4GLD i SEK (2009-12)"), ("Världen", "Storebrand Global All Countries A SEK")]:
    res["assets"][a] = sid

S = {}
S["Original: topp 3, tröskel 2 pe"] = run(ASSETS, START, END)
S["Utan tröskel"] = run(ASSETS, START, END, thr=0.0)
for t in (0.01, 0.03, 0.05):
    S[f"Tröskel {int(t*100)} pe"] = run(ASSETS, START, END, thr=t)
for k in (1, 2, 4, 5):
    S[f"Topp {k}"] = run(ASSETS, START, END, top=k)
for lk in ((3,), (6,), (12,)):
    S[f"Momentum {lk[0]} mån"] = run(ASSETS, START, END, look=lk)
for f, n in (("ma12", "Trendfilter MA12"), ("pos", "Trendfilter positiv avkastning"), ("abs", "Trendfilter absolut momentum")):
    S[n] = run(ASSETS, START, END, filt=f)
S["Utan guld"] = run({k: v for k, v in ASSETS.items() if k != "Guld"}, START, END)
S["Utan ombalansering av kvarvarande"] = run(ASSETS, START, END, rebalance=False)
S["En månads fördröjning (övre gräns)"] = run(ASSETS, START, END, delay=1)
for c in (0.001, 0.0025, 0.005):
    S[f"Extra kostnad {c*100:.2g} % per sida"] = run(ASSETS, START, END, extra_cost=c)

# jämförelser
S["Köp och behåll: världsindex"] = series_bh(WORLD, START, END)
S["60/40 (världen/obligationer)"] = fixed({"Världen": 0.6, "Svenska obligationer": 0.4}, START, END, assets=A)
S["Lika vikt nio tillgångar"] = fixed({k: 1 / 9 for k in ASSETS}, START, END)
S["Köp och behåll: Sverige"] = series_bh(ASSETS["Sverige"], START, END)


def sma_rule(assets, keys, n=10, look=None):
    """SMA-trend per tillgång (månadsvis): investerad om kurs > SMA n mån, annars korta räntor. Lika vikt."""
    ms = months("1984-12", END); lv = {a: gtf.level(assets[a], ms) for a in keys}
    out = {"m": [], "r": [], "w": [], "turn": 0.0, "pos": []}; prev = {}
    for m in months(START, END):
        i = ms.index(m); sm = ms[i - 1]; tw = {}
        for a in keys:
            l = lv[a]; ii = ms.index(sm)
            if look:
                on = l[sm] / l[ms[ii - look]] - 1 > (gtf.level(ASSETS[SHORT], ms)[sm] / gtf.level(ASSETS[SHORT], ms)[ms[ii - look]] - 1)
            else:
                on = l[sm] > sum(l[ms[j]] for j in range(ii - n + 1, ii + 1)) / n
            k = a if on else SHORT; tw[k] = tw.get(k, 0) + 1 / len(keys)
        tc = sum(abs(tw.get(a, 0) - prev.get(a, 0)) * gtf.COST.get(a, 0) for a in set(tw) | set(prev))
        out["turn"] += sum(max(tw.get(a, 0) - prev.get(a, 0), 0) for a in set(tw) | set(prev))
        r = sum(w * (assets[a][m] if a in assets else ASSETS[a][m]) for a, w in tw.items()) - tc
        out["m"].append(m); out["r"].append(r); out["w"].append(tw)
        prev = {a: w * (1 + (assets[a][m] if a in assets else ASSETS[a][m])) / (1 + r) for a, w in tw.items()}
    return out


S["SMA10 mån per tillgång, lika vikt (Faber)"] = sma_rule(ASSETS, [k for k in ASSETS if k != SHORT])
S["SwingEdge-stil: världsindex SMA10 mån (≈SMA200)"] = sma_rule(A, ["Världen"])
S["SwingEdge-stil: världsindex 12 mån TSMOM"] = sma_rule(A, ["Världen"], look=12)
S["SwingEdge-stil: rotation topp 1 Sverige/USA, 12 mån, absolut filter"] = run(
    {k: ASSETS[k] for k in ("Sverige", "USA", SHORT)}, START, END, top=1, thr=0.0, look=(12,), filt="abs")

for n, s in S.items():
    res["strategies"][n] = {"full": metrics(s), "train": metrics(s, b=TRAIN_END), "test": metrics(s, a=TEST_START),
                            "sub": [metrics(s, a=a, b=b) for a, b in SUB],
                            "bl_2010_2025": metrics(s, a="2010-01", b="2025-12"), "since_2018": metrics(s, a="2018-01")}

orig = S["Original: topp 3, tröskel 2 pe"]
# exponering
cnt = {}
for w in orig["w"]:
    for a, x in w.items(): cnt[a] = cnt.get(a, 0) + x
res["exposure"] = {a: v / len(orig["w"]) for a, v in sorted(cnt.items(), key=lambda kv: -kv[1])}
res["current"] = {"signal_month": END, "holdings": list(orig["w"][-1].keys())}

# bootstrap mot jämförelser (hela perioden och testperioden)
def cut(s, a=None):
    idx = [i for i, m in enumerate(s["m"]) if a is None or m >= a]
    return {"m": [s["m"][i] for i in idx], "r": [s["r"][i] for i in idx]}
res["bootstrap"] = {}
for bn in ("Köp och behåll: världsindex", "60/40 (världen/obligationer)", "Lika vikt nio tillgångar"):
    for lab, a in (("full", None), ("test", TEST_START)):
        p, lo, hi = bootstrap_diff(cut(orig, a), cut(S[bn], a))
        res["bootstrap"][f"{bn}|{lab}"] = {"p_not_better": p, "ci90": [lo, hi]}

# variantnät för walk-forward, DSR och PBO
GRID = list(itertools.product((2, 3, 4), (0.0, 0.02, 0.05), ((3, 6, 12), (12,), (6,), (3,)), (None, "ma12")))
G = {g: run(ASSETS, START, END, top=g[0], thr=g[1], look=g[2], filt=g[3]) for g in GRID}
rf = ASSETS[SHORT]
srs = [gtf.sharpe_ex(s["r"], s["m"]) / math.sqrt(12) for s in G.values()]
mu = sum(srs) / len(srs); var = sum((x - mu) ** 2 for x in srs) / (len(srs) - 1)
ex = [x - rf[m] for x, m in zip(orig["r"], orig["m"])]
res["dsr_original"] = dsr(ex, len(GRID), var)
bm = S["Köp och behåll: världsindex"]
act = [x - y for x, y in zip(orig["r"], bm["r"])]
mu_a = sum(act) / len(act); sd_a = math.sqrt(sum((x - mu_a) ** 2 for x in act) / (len(act) - 1))
res["active_vs_world"] = {"mean_annual": mu_a * 12, "te": sd_a * math.sqrt(12), "ir": mu_a / sd_a * math.sqrt(12)}
res["pbo"] = pbo([[x - rf[m] for x, m in zip(s["r"], s["m"])] for s in G.values()])
res["grid_size"] = len(GRID)
res["grid_sharpe_range"] = [min(srs) * math.sqrt(12), max(srs) * math.sqrt(12)]
rank = sorted(G, key=lambda g: -gtf.sharpe_ex(G[g]["r"], G[g]["m"]))
res["original_rank_in_grid"] = rank.index((3, 0.02, (3, 6, 12), None)) + 1

# walk-forward: välj varje januari den variant som haft bäst Sharpe på all tidigare data (minst 7 år)
wf = {"m": [], "r": [], "w": [], "turn": 0.0, "pos": []}; picks = []
for y in range(2010, int(END[:4]) + 1):
    hist_end = f"{y-1}-12"
    best = max(GRID, key=lambda g: (lambda s: gtf.sharpe_ex([s["r"][i] for i, m in enumerate(s["m"]) if m <= hist_end],
                                                              [m for m in s["m"] if m <= hist_end]))(G[g]))
    picks.append((y, best))
    for i, m in enumerate(G[best]["m"]):
        if m[:4] == str(y): wf["m"].append(m); wf["r"].append(G[best]["r"][i])
res["walk_forward"] = {"picks": [(y, list(map(str, g))) for y, g in picks], "wf": metrics(wf),
                       "original_same": metrics(orig, a="2010-01")}

# Spearman: träning mot test i variantnätet
def spearman(x, y):
    rx = {v: i for i, v in enumerate(sorted(range(len(x)), key=lambda k: x[k]))}
    ry = {v: i for i, v in enumerate(sorted(range(len(y)), key=lambda k: y[k]))}
    n = len(x); d = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1 - 6 * d / (n * (n * n - 1))
tr = [metrics(G[g], b=TRAIN_END)["sharpe"] for g in GRID]; te = [metrics(G[g], a=TEST_START)["sharpe"] for g in GRID]
res["spearman_train_test"] = spearman(tr, te)
json.dump(res, open("results_gtf.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)

def f(x, p=1): return "–" if x is None else f"{x*100:.{p}f}"
print(f"{'Strategi':58} {'CAGR':>6} {'Vol':>5} {'Shp':>5} {'Sort':>5} {'MDD':>6} {'Oms':>5} | test CAGR Shp MDD | 2018– CAGR Shp MDD")
for n, v in res["strategies"].items():
    a, t, l = v["full"], v["test"], v["since_2018"]
    print(f"{n[:58]:58} {f(a['cagr']):>6} {f(a['vol']):>5} {a['sharpe']:5.2f} {a['sortino']:5.2f} {f(a['maxdd'],0):>6} {f(a['turnover'],0):>5} | {f(t['cagr']):>5} {t['sharpe']:4.2f} {f(t['maxdd'],0):>4} | {f(l['cagr']):>5} {l['sharpe']:4.2f} {f(l['maxdd'],0):>4}")
for k in ("bootstrap", "dsr_original", "pbo", "spearman_train_test", "original_rank_in_grid", "grid_sharpe_range", "active_vs_world", "exposure", "current"):
    print(k, json.dumps(res[k], ensure_ascii=False, default=str)[:600])
print("WF", res["walk_forward"]["wf"]["cagr"], res["walk_forward"]["wf"]["sharpe"], res["walk_forward"]["wf"]["maxdd"], "| orig", res["walk_forward"]["original_same"]["cagr"], res["walk_forward"]["original_same"]["sharpe"], res["walk_forward"]["original_same"]["maxdd"])
print(res["walk_forward"]["picks"])
