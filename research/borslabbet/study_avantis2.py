"""Längre test av Avantis-kärnan: Dimensional-fonder (samma forskningsmetod) som proxy från 2003–2005,
kombinerat med SwingEdge från jun 2015. Alla andelar 25/50/75 % redovisas (inget val på testdata).
Skriver results_avantis2.json."""
import json, sys, math, os, time
sys.stdout.reconfigure(encoding="utf-8")
import gtf
from study_ext import yahoo
from swingedge_series import load_swingedge

CACHE = "data/avantis2.json"
SYMS = ["DGEIX", "DFSVX", "DISVX", "DFCEX", "ACWI", "AVUS", "AVDE", "AVEM", "AVUV", "AVDV"]
data = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
for s in SYMS:
    if s not in data: data[s] = yahoo(s); time.sleep(0.4)
json.dump(data, open(CACHE, "w", encoding="utf-8"))
R = {s: gtf.rets(gtf.ffill(data[s], gtf.Y["SEK=X"])) for s in SYMS}
def mix(w, ms): return {m: sum(x * R[k][m] for k, x in w.items()) for m in ms}
def corr(a, b, ms):
    x = [a[m] for m in ms]; y = [b[m] for m in ms]; mx, my = sum(x) / len(x), sum(y) / len(y)
    return sum((p - mx) * (q - my) for p, q in zip(x, y)) / math.sqrt(sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y))
def met(r, ms, a=None, b=None):
    mm = [m for m in ms if (a is None or m >= a) and (b is None or m <= b)]
    return gtf.metrics({"m": mm, "r": [r[m] for m in mm], "w": [], "turn": 0.0, "pos": []})

allm = gtf.months("2005-06", gtf.LAST)
ms = [m for m in allm if all(m in R[s] for s in ["DGEIX", "DFSVX", "DISVX", "DFCEX"])]
DFA = mix({"DGEIX": 1 / 3, "DFSVX": 0.2, "DISVX": 2 / 15, "DFCEX": 1 / 3}, ms)   # tredjedelar; småbolagsvärde 60/40 USA/övriga
# proxyns kvalitet mot Avantis-trion (amerikanska fonder) där båda finns
ov = [m for m in ms if all(m in R[s] for s in ["AVUS", "AVDE", "AVEM", "AVUV", "AVDV"])]
AV = mix({"AVUS": .62 / 3, "AVDE": .28 / 3, "AVEM": .10 / 3 + 1 / 3, "AVUV": .2, "AVDV": 2 / 15}, ov)
res = {"proxy_vs_avantis": {"months": len(ov), "corr": corr({m: DFA[m] for m in ov}, AV, ov),
                            "dfa": met(DFA, ov), "avantis": met(AV, ov)}}
# Avantis-proxyn ensam mot världsindex, från ACWI:s start
ms_w = [m for m in ms if m in R["ACWI"]]
res["core_vs_world"] = {"core": met(DFA, ms_w), "world": met(R["ACWI"], ms_w), "core_2008": met(DFA, ms_w, b="2009-12")}
p, lo, hi = gtf.bootstrap_diff({"m": ms_w, "r": [DFA[m] for m in ms_w]}, {"m": ms_w, "r": [R["ACWI"][m] for m in ms_w]})
res["core_vs_world"]["p_not_better"] = p

SE = load_swingedge()
mc = [m for m in ms if all(m in v for v in SE.values())]
C = {"SwingEdge 20/40/40": SE["SwingEdge 20/40/40"], "SwingEdge med guld": SE["SwingEdge med guld"], "Avantis-kärna ensam (proxy)": DFA}
for a in (0.25, 0.5, 0.75):
    C[f"{int(a*100)} % Avantis + SwingEdge"] = {m: a * DFA[m] + (1 - a) * SE["SwingEdge 20/40/40"][m] for m in mc}
    C[f"{int(a*100)} % Avantis + SwingEdge med guld"] = {m: a * DFA[m] + (1 - a) * SE["SwingEdge med guld"][m] for m in mc}
SUB = [("2015-06", "2019-12"), ("2020-01", "2022-12"), ("2023-01", gtf.LAST)]
res["period"] = [mc[0], mc[-1]]; res["combo"] = {}
for n, r in C.items():
    res["combo"][n] = {"full": met(r, mc), "sub": [met(r, mc, a, b) for a, b in SUB]}
for n in [k for k in C if "%" in k]:
    base = "SwingEdge med guld" if "guld" in n else "SwingEdge 20/40/40"
    p, lo, hi = gtf.bootstrap_diff({"m": mc, "r": [C[n][m] for m in mc]}, {"m": mc, "r": [C[base][m] for m in mc]})
    res["combo"][n]["p_not_better_than_swingedge"] = p; res["combo"][n]["ci90"] = [lo, hi]
res["corr_core_swingedge"] = corr(DFA, SE["SwingEdge 20/40/40"], mc)
json.dump(res, open("results_avantis2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
pv = res["proxy_vs_avantis"]; print("proxy mot Avantis", pv["months"], "mån, korr", round(pv["corr"], 3), "| DFA", round(pv["dfa"]["cagr"]*100, 1), round(pv["dfa"]["sharpe"], 2), "| Avantis", round(pv["avantis"]["cagr"]*100, 1), round(pv["avantis"]["sharpe"], 2))
cw = res["core_vs_world"]; print("kärna mot ACWI", cw["core"]["from"], cw["core"]["cagr"], cw["core"]["sharpe"], cw["core"]["maxdd"], "| ACWI", cw["world"]["cagr"], cw["world"]["sharpe"], cw["world"]["maxdd"], "| p", cw["p_not_better"])
print("period", res["period"], "korr kärna/SwingEdge", round(res["corr_core_swingedge"], 2))
for n, v in res["combo"].items():
    f = v["full"]; s = " | ".join(f"{x['cagr']*100:.0f}/{x['sharpe']:.2f}/{x['maxdd']*100:.0f}" for x in v["sub"])
    print(f"{n:40} {f['cagr']*100:5.1f} {f['sharpe']:.2f} {f['maxdd']*100:4.0f} | {s} | p {v.get('p_not_better_than_swingedge', '–')}")
