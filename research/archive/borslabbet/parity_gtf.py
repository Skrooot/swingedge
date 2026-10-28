"""Facit för appens Global Allocation: samma nio Avanza-produkter som appen använder, originalreglerna.
Skriver swingedge/app/src/test/resources/gtf_parity.json."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
import gtf
F = gtf.F
IMPL = {"SE": 159608, "EU": 581, "US": 1505, "JP": 1263, "EM": 487076, "SMB": 789175, "BOND": 2098, "SHORT": 2028}
levels = {k: {m: v for m, v in F[str(i)]["series"].items() if m <= gtf.LAST} for k, i in IMPL.items()}
levels["GOLD"] = {m: v for m, v in gtf.ffill(gtf.Y["4GLD.DE"], gtf.Y["EURSEK=X"]).items() if m <= gtf.LAST}
assets = {k: gtf.rets(v) for k, v in levels.items()}
ms = gtf.months("2000-01", "2026-10")
# första signalmånad där alla nio har 12 månaders avkastning
first = next(m for i, m in enumerate(ms) if i >= 12 and all(all(ms[j] in assets[a] for j in range(i - 11, i + 1)) for a in assets))
start = ms[ms.index(first) + 1]
res = gtf.run(assets, start, "2026-10")  # sista beslutet (signal sep 2026) gäller oktober
decisions = [{"signalMonth": ms[ms.index(m) - 1], "holdings": sorted(w)} for m, w in zip(res["m"], res["w"])]
json.dump({"levels": levels, "decisions": decisions, "first": first}, open("C:/Users/fredrik/android-build/swingedge/app/src/test/resources/gtf_parity.json", "w", encoding="utf-8"))
print(first, len(decisions), decisions[-1], gtf.metrics(res))
