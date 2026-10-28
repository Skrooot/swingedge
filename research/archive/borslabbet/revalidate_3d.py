"""Validering av SwingEdge med guld när Bitcoin Trend får tredagarsregeln (Rules.CRYPTO_CONFIRM = 3).
Samma motor och mått som strategins RESULTS (study3.py via swingedge_series, månadsavkastning i SEK, gtf.metrics),
samt block-bootstrap av skillnaden mot den dagliga regeln."""
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
import swingedge_series as SS, gtf
from gtf import bootstrap_diff
A, B = SS.load_swingedge(1), SS.load_swingedge(3)
def res(r, ms): return {"m": ms, "r": [r[m] for m in ms], "w": [], "turn": 0.0, "pos": []}
out = {}
for lab, a0, b0 in (("jun 2015 – sep 2026", "2015-06", "2026-09"), ("jan 2020 – sep 2026", "2020-01", "2026-09"), ("jun 2015 – dec 2019", "2015-06", "2019-12")):
    for name in ("SwingEdge med guld", "Bitcoin Trend (hink)"):
        ms = [m for m in sorted(A[name]) if a0 <= m <= b0 and m in B[name]]
        x, y = gtf.metrics(res(A[name], ms)), gtf.metrics(res(B[name], ms))
        print(f"{lab:20} {name:22} daglig {x['cagr']*100:5.1f} % Sh {x['sharpe']:.2f} DD {x['maxdd']*100:4.0f} % | 3 dagar {y['cagr']*100:5.1f} % Sh {y['sharpe']:.2f} DD {y['maxdd']*100:4.0f} %")
        out[f"{name} {lab}"] = {"daily": x, "confirm3": y}
ms = [m for m in sorted(A["SwingEdge med guld"]) if "2015-06" <= m <= "2026-09"]
p, lo, hi = bootstrap_diff(res(B["SwingEdge med guld"], ms), res(A["SwingEdge med guld"], ms))
print("bootstrap: p (3 dagar inte bättre Sharpe än daglig)", p, "intervall", lo, hi)
json.dump(out, open("results_3d.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
