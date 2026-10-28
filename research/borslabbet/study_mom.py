"""Forskningsvariant av Sammansatt momentum på dagens Large + Mid Cap Stockholm (pris utan utdelningar).

Begränsningar (därför kan resultatet INTE verifiera Börslabbets strategi):
- Universumet är dagens noterade bolag: överlevnadsbias (avnoterade och uppköpta bolag saknas).
- Yahoo-stängning är utan utdelningar. Jämförelsen görs därför främst mot lika vikt i samma universum.
- F-score kräver historiska bokslut med publiceringsdatum; sådana data finns inte här. Filtret ersätts
  inte med något påhittat; varianten 'med F-score' saknas.
Skriver results_mom.json.
"""
import json, os, re, sys, math, itertools
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "C:/Users/fredrik/android-build/qa/swing")
import engine as E
import gtf

COST = 0.003            # per sida: courtage 0,069 % + halva spreaden i Large/Mid Cap, avrundat uppåt
LIQ = 2_000_000         # median dagsomsättning (kr) senaste 3 mån, punkt-i-tid-filter
START, END = "2006-01", gtf.LAST
TRAIN_END, TEST_START = "2015-12", "2016-01"

src = open("C:/Users/fredrik/android-build/kryptosentiment/www/stocks.js", encoding="utf-8").read()
rows = re.findall(r'\["([A-Z0-9-]+\.ST)", "([^"]+)", "([LM])"', src)
by = {}
for sym, name, seg in rows:
    base = re.sub(r"\s+(A|B|C|D|SDB|ser\. ?[AB])$", "", name).strip()
    if base not in by or sym.endswith("-B.ST"): by[base] = sym
MON = {}   # sym -> {månad: (stängning, median omsättning 63 d)}
for sym in sorted(by.values()):
    p = f"C:/Users/fredrik/android-build/qa/swing/data/{sym}.json"
    if not os.path.exists(p): continue
    r = json.load(open(p, encoding="utf-8"))["rows"][20:]   # bort med de första 20 dagarna efter notering
    if len(r) < 300: continue
    c = [r[0][4]]; to = []
    for i in range(1, len(r)):
        c.append(c[-1] * (1 + max(-0.5, min(1.0, r[i][4] / r[i - 1][4] - 1))))
    m = {}
    for i, row in enumerate(r):
        to.append(row[4] * (row[5] or 0))
        if i + 1 == len(r) or r[i + 1][0][:7] != row[0][:7]:
            w = sorted(to[-63:]); m[row[0][:7]] = (c[i], w[len(w) // 2])
    MON[sym] = m
print("aktier", len(MON))
MS = gtf.months("2004-01", END)
RF = gtf.ASSETS["Svenska korta räntor"]
SWE = gtf.ASSETS["Sverige"]
swe_lv = gtf.level(SWE, MS)


def score(sym, i, look):
    m = MON[sym]; vals = []
    for n in look:
        a, b = MS[i - n], MS[i]
        if a not in m or b not in m: return None
        vals.append(m[b][0] / m[a][0] - 1)
    return sum(vals) / len(vals)


def run(look=(3, 6, 12), top=10, freq="M", band=None, trend=False, cost=COST, sign=1):
    out = {"m": [], "r": [], "w": [], "turn": 0.0, "pos": []}; hold = []; w = {}
    for m in gtf.months(START, END):
        i = MS.index(m); sm = MS[i - 1]; si = i - 1
        reb = freq == "M" or (freq == "Q" and sm[5:] in ("02", "05", "08", "11")) or (freq == "Y" and sm[5:] == "02")
        univ = [s for s in MON if sm in MON[s] and MON[s][sm][1] >= LIQ and MS[si - 12] in MON[s]]
        if reb or not hold:
            sc = {s: score(s, si, look) for s in univ}; sc = {s: v for s, v in sc.items() if v is not None}
            rank = sorted(sc, key=lambda s: -sign * sc[s])
            if band:
                keep = [s for s in hold if s in rank[:band]]
                new = keep + [s for s in rank if s not in keep][:top - len(keep)]
            else:
                new = rank[:top]
            on = True
            if trend:
                on = swe_lv[sm] > sum(swe_lv[MS[j]] for j in range(si - 9, si + 1)) / 10
            tw = {s: 1 / len(new) for s in new} if on and new else {"_rf": 1.0}
        else:
            tw = w
        tc = sum(abs(tw.get(a, 0) - w.get(a, 0)) for a in set(tw) | set(w)) * cost
        out["turn"] += sum(max(tw.get(a, 0) - w.get(a, 0), 0) for a in set(tw) | set(w))
        def ret(a):
            if a == "_rf": return RF[m]
            x = MON[a]; return x[m][0] / x[sm][0] - 1 if m in x and sm in x else 0.0
        r = sum(wt * ret(a) for a, wt in tw.items()) - tc
        out["m"].append(m); out["r"].append(r); out["w"].append(tw)
        w = {a: wt * (1 + ret(a)) / (1 + r) for a, wt in tw.items()} if r > -1 else {}
        hold = [a for a in w if a != "_rf"]
    return out


def ew():
    out = {"m": [], "r": [], "w": [], "turn": 0.0, "pos": []}
    for m in gtf.months(START, END):
        i = MS.index(m); sm = MS[i - 1]
        univ = [s for s in MON if sm in MON[s] and m in MON[s] and MON[s][sm][1] >= LIQ and MS[i - 13] in MON[s]]
        out["m"].append(m); out["r"].append(sum(MON[s][m][0] / MON[s][sm][0] - 1 for s in univ) / len(univ))
    return out


S = {"Lika vikt, samma universum (månadsvis)": ew(), "Sverige-fond (med utdelningar)": gtf.series_bh(SWE, START, END)}
for look, n in (((3, 6, 12), "Sammansatt 3/6/12"), ((3,), "3 mån"), ((6,), "6 mån"), ((12,), "12 mån")):
    S[f"{n}, topp 10, månadsvis"] = run(look)
S["Sammansatt, topp 10, kvartalsvis"] = run(freq="Q")
S["Sammansatt, topp 10, årsvis"] = run(freq="Y")
S["Sammansatt, topp 10, månadsvis, banding topp 20 (Börslabbets momentumportfölj)"] = run(band=20)
S["Sammansatt, topp 10, kvartalsvis, banding topp 20"] = run(freq="Q", band=20)
S["Sammansatt, topp 5, månadsvis, banding topp 10"] = run(top=5, band=10)
S["Sammansatt, topp 20, månadsvis, banding topp 40"] = run(top=20, band=40)
S["Sammansatt, topp 10, banding 20, trendfilter (Sverige > SMA10)"] = run(band=20, trend=True)
S["Lägst sammansatt momentum, topp 10, kvartalsvis"] = run(freq="Q", sign=-1)
S["Sammansatt, topp 10, banding 20, utan kostnader"] = run(band=20, cost=0.0)

res = {"n_stocks": len(MON), "liq": LIQ, "cost": COST, "period": [START, END], "strategies": {}}
ewr = S["Lika vikt, samma universum (månadsvis)"]
for n, s in S.items():
    p = gtf.bootstrap_diff(s, ewr) if not n.startswith("Lika") else None
    res["strategies"][n] = {"full": gtf.metrics(s), "train": gtf.metrics(s, b=TRAIN_END), "test": gtf.metrics(s, a=TEST_START),
                            "p_not_better_than_ew": p[0] if p else None}
    f, t = res["strategies"][n]["full"], res["strategies"][n]["test"]
    print(f"{n[:66]:66} {f['cagr']*100:5.1f} {f['sharpe']:5.2f} {f['maxdd']*100:4.0f} oms {f['turnover']*100:4.0f} | träning {res['strategies'][n]['train']['sharpe']:.2f} test {t['cagr']*100:5.1f} {t['sharpe']:5.2f} {t['maxdd']*100:4.0f} | p {p[0] if p else '–'}")
json.dump(res, open("results_mom.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
