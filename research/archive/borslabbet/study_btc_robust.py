"""Robusthet för Bitcoin Trend-varianterna: varje familj körs över ett rutnät av SMA-längder och filterstyrkor,
på delperioder (2015–17, 2018–20, 2021–23, 2024–26) och på ETH-USD som inte användes vid valet av regeln.
Samma motor som study_btc_whipsaw.py: signal på stängning, position nästa dag, 0,40 % per sida, kontanter 0 %."""
import json, math, sys, statistics, datetime
sys.stdout.reconfigure(encoding="utf-8")

def load(sym):
    rows = [(r[0], r[4]) for r in json.load(open(f"C:/Users/fredrik/android-build/qa/swing/data/{sym}.json", encoding="utf-8"))["rows"] if r[4]]
    return [d for d, _ in rows], [c for _, c in rows]

COST = 0.004

def rule(D, C, n, band=0.0, confirm=1, check=None):
    s, on, streak, st = 0.0, False, 0, []
    for i, c in enumerate(C):
        s += c
        if i >= n: s -= C[i - n]
        if i < n - 1: st.append(False); continue
        m = s / n
        flip = c < m * (1 - band) if on else c > m * (1 + band)
        streak = streak + 1 if flip else 0
        if (check is None or check(D, i)) and streak >= confirm: on = not on; streak = 0
        st.append(on)
    return st

def week_end(D, i): return datetime.date.fromisoformat(D[i]).weekday() == 6
def month_end(D, i): return i + 1 < len(D) and D[i + 1][:7] != D[i][:7]

def run(D, C, st, a, b):
    eq, peak, dd, rets, tr, was = 1.0, 1.0, 0.0, [], 0, None
    for i in range(1, len(C)):
        if not (a <= D[i] <= b): continue
        pos = st[i - 1]; r = (C[i] / C[i - 1] - 1) if pos else 0.0
        if was is not None and pos != was: r -= COST; tr += 1
        was = pos; eq *= 1 + r; peak = max(peak, eq); dd = min(dd, eq / peak - 1); rets.append(r)
    n = len(rets); mu = sum(rets) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in rets) / (n - 1))
    return {"cagr": eq ** (365.25 / n) - 1, "sh": mu / sd * math.sqrt(365), "dd": dd, "tr": tr / (n / 365.25)}

NS = [100, 125, 150, 175, 200]
FAM = {
    "Daglig (appen)":            [dict()],
    "N stängningar i rad":       [dict(confirm=k) for k in (2, 3, 4, 5)],
    "Band runt linjen":          [dict(band=b) for b in (0.02, 0.03, 0.05, 0.08)],
    "Kontroll varje söndag":     [dict(check=week_end)],
    "Kontroll vid månadsslut":   [dict(check=month_end)],
}
SUB = [("2015-06-01", "2017-12-31"), ("2018-01-01", "2020-12-31"), ("2021-01-01", "2023-12-31"), ("2024-01-01", "2026-12-31")]
data = {"BTC": load("BTC-USD"), "ETH": load("ETH-USD")}
bh = {k: run(D, C, [True] * len(C), "2015-06-01" if k == "BTC" else "2017-11-09", D[-1]) for k, (D, C) in data.items()}

print("Varje rad: alla SMA-längder 100–200 x alla filterstyrkor i familjen.")
print("Sharpe median / sämsta, andel inställningar som slår köp och behåll på Sharpe, sämsta delperiod-Sharpe (BTC), affärer/år, ETH Sharpe median / sämsta")
print(f"köp och behåll Sharpe: BTC {bh['BTC']['sh']:.2f} (maxDD {bh['BTC']['dd']*100:.0f} %), ETH {bh['ETH']['sh']:.2f} (maxDD {bh['ETH']['dd']*100:.0f} %)\n")
for fam, ps in FAM.items():
    btc, eth, subw, trs, dds = [], [], [], [], []
    for n in NS:
        for p in ps:
            D, C = data["BTC"]; st = rule(D, C, n, **p)
            r = run(D, C, st, "2015-06-01", D[-1]); btc.append(r["sh"]); trs.append(r["tr"]); dds.append(r["dd"])
            subw.append(min(run(D, C, st, a, b)["sh"] for a, b in SUB))
            D, C = data["ETH"]; st = rule(D, C, n, **p)
            eth.append(run(D, C, st, "2017-11-09", D[-1])["sh"])
    beat = sum(x > bh["BTC"]["sh"] for x in btc) / len(btc)
    print(f"{fam:26} BTC Sh {statistics.median(btc):.2f} / {min(btc):.2f}  slår B&H {beat*100:3.0f} %  "
          f"sämsta delperiod {min(subw):5.2f}  maxDD median {statistics.median(dds)*100:4.0f} %  aff/år {statistics.median(trs):4.1f}  "
          f"| ETH Sh {statistics.median(eth):.2f} / {min(eth):.2f}  (n={len(btc)})")
