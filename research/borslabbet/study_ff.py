"""Oberoende test av faktorprinciperna (värde, momentum, kvalitet/lönsamhet) med Ken Frenchs dataset.
Datan är punkt-i-tid-konstruerad av French (Bloomberg/Compustat-baserad, med avnoterade bolag), men det är
breda portföljer (topp 30 %), inte Börslabbets topp-10-strategier, och utan handelskostnader.
Skriver results_ff.json."""
import json, math, sys
sys.stdout.reconfigure(encoding="utf-8")
D = "ff/"


def stats(r, rf=None):
    n = len(r); eq = peak = 1.0; mdd = 0.0
    for x in r:
        eq *= 1 + x; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    ex = [x - (rf[i] if rf else 0) for i, x in enumerate(r)]
    mu = sum(ex) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in ex) / (n - 1))
    return {"cagr": eq ** (12 / n) - 1, "vol": sd * math.sqrt(12), "sharpe": mu / sd * math.sqrt(12), "maxdd": mdd, "months": n}


def tstat(d):
    n = len(d); mu = sum(d) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in d) / (n - 1))
    return mu * 12, mu / sd * math.sqrt(n)


def sweden():
    L = open(D + "Sweden.Dat", encoding="latin-1").read().splitlines()
    # andra blocket: Value-Weight Local Returns, alla bolag (inte alla fyra nyckeltal krävs)
    start = next(i for i, l in enumerate(L) if "Value-Weight Local  Returns" in l and "Not Reqd" in l)
    rows = {}
    for l in L[start + 3:]:
        p = l.split()
        if len(p) < 10 or not p[0].isdigit() or len(p[0]) != 6: break
        rows[p[0][:4] + "-" + p[0][4:]] = [float(x) / 100 if float(x) > -99 else None for x in p[1:]]
    cols = ["Mkt", "BM_H", "BM_L", "EP_H", "EP_L", "CEP_H", "CEP_L", "Y_H", "Y_L", "Y_0"]
    return {m: dict(zip(cols, v)) for m, v in rows.items()}


def ff_csv(name, cols_want=None):
    L = open(D + name, encoding="latin-1").read().splitlines()
    i = next(k for k, l in enumerate(L) if l.startswith(","))
    head = [h.strip() for h in L[i].split(",")]
    out = {}
    for l in L[i + 1:]:
        p = [x.strip() for x in l.split(",")]
        if not p[0].isdigit() or len(p[0]) != 6: break
        out[p[0][:4] + "-" + p[0][4:]] = {h: float(x) / 100 for h, x in zip(head[1:], p[1:])}
    return out


res = {"sweden": {}, "europe": {}}
sw = sweden()
PER = [("1975-01", "1999-12"), ("2000-01", "2009-12"), ("2010-01", "2026-12"), ("1975-01", "2026-12")]
for a, b in PER:
    ms = [m for m in sorted(sw) if a <= m <= b]
    row = {"Marknad": stats([sw[m]["Mkt"] for m in ms])}
    for k, n in (("BM_H", "Högt B/M (billigast 30 %)"), ("EP_H", "Högt E/P"), ("CEP_H", "Högt kassaflöde/pris"), ("Y_H", "Hög direktavkastning"),
                 ("BM_L", "Lågt B/M (dyrast 30 %)")):
        mm = [m for m in ms if sw[m][k] is not None]
        s = stats([sw[m][k] for m in mm]); d = [sw[m][k] - sw[m]["Mkt"] for m in mm]
        s["excess_vs_mkt"], s["t"] = tstat(d); row[n] = s
    res["sweden"][f"{a[:4]}–{min(b[:4], '2026')}"] = row

f5 = ff_csv("Europe_5_Factors.csv"); mom = ff_csv("Europe_MOM_Factor.csv")
p_mom = ff_csv("Europe_6_Portfolios_ME_Prior_12_2.csv"); p_op = ff_csv("Europe_6_Portfolios_ME_OP.csv"); p_bm = ff_csv("Europe_6_Portfolios_ME_BE-ME.csv")
EPER = [("1990-11", "2009-12"), ("2010-01", "2026-12"), ("1990-11", "2026-12")]
for a, b in EPER:
    ms = [m for m in sorted(p_mom) if a <= m <= b and m in f5 and m in p_op and m in p_bm and m in mom]
    rf = [f5[m]["RF"] for m in ms]
    mkt = [f5[m]["Mkt-RF"] + f5[m]["RF"] for m in ms]
    row = {"Marknad (USD)": stats(mkt, rf)}
    for src, col, n in ((p_mom, "BIG HiPRIOR", "Stora bolag, högt momentum"), (p_mom, "SMALL HiPRIOR", "Små bolag, högt momentum"),
                        (p_op, "BIG HiOP", "Stora bolag, hög lönsamhet"), (p_op, "SMALL HiOP", "Små bolag, hög lönsamhet"),
                        (p_bm, "BIG HiBM", "Stora bolag, högt B/M"), (p_bm, "SMALL HiBM", "Små bolag, högt B/M"),
                        (p_mom, "BIG LoPRIOR", "Stora bolag, lågt momentum")):
        r = [src[m][col] for m in ms]; s = stats(r, rf); s["excess_vs_mkt"], s["t"] = tstat([x - y for x, y in zip(r, mkt)]); row[n] = s
    for k, n in (("HML", "HML (värde, lång–kort)"), ("RMW", "RMW (lönsamhet, lång–kort)")):
        row[n] = dict(zip(("mean", "t"), tstat([f5[m][k] for m in ms])))
    row["MOM (momentum, lång–kort)"] = dict(zip(("mean", "t"), tstat([mom[m][next(iter(mom[m]))] for m in ms])))
    res["europe"][f"{a[:4]}–{b[:4]}"] = row

json.dump(res, open("results_ff.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for reg in ("sweden", "europe"):
    for per, row in res[reg].items():
        print("==", reg, per)
        for n, s in row.items():
            if "cagr" in s:
                print(f"  {n:34} CAGR {s['cagr']*100:5.1f} Sharpe {s['sharpe']:5.2f} MDD {s['maxdd']*100:4.0f}" + (f" | mot marknad {s['excess_vs_mkt']*100:+5.1f} %/år t={s['t']:.1f}" if "t" in s else ""))
            else:
                print(f"  {n:34} {s['mean']*100:+5.1f} %/år t={s['t']:.1f}")
