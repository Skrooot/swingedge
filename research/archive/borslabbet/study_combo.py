"""Kombinationer: SwingEdges befintliga hinkar + Global trendföljning (+ momentumvarianten). Skriver results_combo.json."""
import json, sys, os, io, contextlib, math
sys.stdout.reconfigure(encoding="utf-8")
import gtf
SW = "C:/Users/fredrik/android-build/qa/swing"


def load_swingedge():
    """Kör study3.py:s simulering (utan att skriva om dess resultatfil) och returnerar månadsavkastningar i SEK."""
    cwd = os.getcwd(); os.chdir(SW); sys.path.insert(0, SW)
    ns = {"__name__": "study3_import", "__file__": f"{SW}/study3.py"}
    real = json.dump
    json.dump = lambda *a, **k: None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(open(f"{SW}/study3.py", encoding="utf-8").read(), ns)
    finally:
        json.dump = real; os.chdir(cwd)
    def monthly(res):
        out = {}
        for d, r in zip(res["dates"], res["r"]):
            out.setdefault(d[:7], 1.0); out[d[:7]] *= 1 + r
        ks = sorted(out)
        return {k: v - 1 for k, v in out.items() if k != ks[0] and k != ks[-1]}  # bort med ofullständiga kantmånader
    s = ns["system"]
    return {"SwingEdge 20/40/40": monthly(ns["sys_res"]["SwingEdge 20/40/40 (nuvarande)"]),
            "SwingEdge med guld": monthly(ns["sys_res"]["SwingEdge med guld i lika vikt"]),
            "Bitcoin Trend (hink)": monthly(s(ns["BASE"], sleeves=(1.0, 0.0, 0.0))),
            "S&P 500 Trend (hink)": monthly(s(ns["BASE"], sleeves=(0.0, 0.0, 1.0))),
            "Lika vikt (hink)": monthly(ns["equal"](ns["BASE"]))}


SE = load_swingedge()
G = gtf.run(gtf.ASSETS, "2002-08", gtf.LAST); GTF = dict(zip(G["m"], G["r"]))
import importlib
sm = importlib.import_module("study_mom")  # kör om momentumstudien (deterministisk)
mm = sm.run(band=20); MOM = dict(zip(mm["m"], mm["r"]))
WORLD = gtf.WORLD; RF = gtf.ASSETS["Svenska korta räntor"]

BASE = {"Global trendföljning": GTF, "Momentum (forskningsvariant, överlevnadsbias)": MOM, "Världsindex": WORLD, **SE}
common = sorted(set.intersection(*[set(v) for v in BASE.values()]) & set(gtf.months("2000-01", gtf.LAST)))
print("gemensam period", common[0], common[-1], len(common))


def mix(w):
    return {m: sum(x * BASE[k][m] for k, x in w.items()) for m in common}


C = dict(BASE)
C["50 % SwingEdge + 50 % Global trendföljning"] = mix({"SwingEdge 20/40/40": 0.5, "Global trendföljning": 0.5})
C["SwingEdge med GTF i stället för lika vikt (20 BTC / 40 GTF / 40 S&P)"] = mix({"Bitcoin Trend (hink)": 0.2, "Global trendföljning": 0.4, "S&P 500 Trend (hink)": 0.4})
C["20 % Bitcoin Trend + 80 % Global trendföljning"] = mix({"Bitcoin Trend (hink)": 0.2, "Global trendföljning": 0.8})
C["50 % Global trendföljning + 50 % momentum"] = mix({"Global trendföljning": 0.5, "Momentum (forskningsvariant, överlevnadsbias)": 0.5})
C["Global trendföljning + aktietrend (50/50 GTF / S&P 500 Trend)"] = mix({"Global trendföljning": 0.5, "S&P 500 Trend (hink)": 0.5})
C["Tredjedelar: SwingEdge / GTF / momentum"] = mix({"SwingEdge 20/40/40": 1 / 3, "Global trendföljning": 1 / 3, "Momentum (forskningsvariant, överlevnadsbias)": 1 / 3})

res = {"period": [common[0], common[-1]], "metrics": {}, "corr": {}, "bootstrap": {}}
for n, r in C.items():
    s = {"m": common, "r": [r[m] for m in common], "w": [], "turn": 0.0, "pos": []}
    res["metrics"][n] = gtf.metrics(s)
    x = res["metrics"][n]
    print(f"{n[:70]:70} CAGR {x['cagr']*100:5.1f} vol {x['vol']*100:5.1f} Sharpe {x['sharpe']:.2f} Sortino {x['sortino']:.2f} MDD {x['maxdd']*100:4.0f}")


def corr(a, b):
    x = [a[m] for m in common]; y = [b[m] for m in common]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    return sum((p - mx) * (q - my) for p, q in zip(x, y)) / math.sqrt(sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y))


ks = list(BASE)
for i, a in enumerate(ks):
    for b in ks[i + 1:]:
        res["corr"][f"{a} | {b}"] = corr(BASE[a], BASE[b])
for a, b in (("50 % SwingEdge + 50 % Global trendföljning", "SwingEdge 20/40/40"),
             ("SwingEdge med GTF i stället för lika vikt (20 BTC / 40 GTF / 40 S&P)", "SwingEdge 20/40/40"),
             ("Global trendföljning", "Världsindex")):
    sa = {"m": common, "r": [C[a][m] for m in common]}; sb = {"m": common, "r": [C[b][m] for m in common]}
    p, lo, hi = gtf.bootstrap_diff(sa, sb)
    res["bootstrap"][f"{a} mot {b}"] = {"p_not_better": p, "ci90": [lo, hi]}
# gemensamma förlustmånader: andel månader där båda förlorar mer än 3 %
res["joint_losses"] = {f"GTF & {k}": sum(1 for m in common if GTF[m] < -0.03 and BASE[k][m] < -0.03) / len(common) for k in ks if k != "Global trendföljning"}
json.dump(res, open("results_combo.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res["corr"], ensure_ascii=False, indent=0)[:1600]); print(res["bootstrap"]); print(res["joint_losses"])
