"""Faber 10 mån (±0/2/5 % band) mot SMA150 + 3 dagar per kategori, och för BTC-USD separat (från study_filters.py)."""
import sys, statistics, io, contextlib
sys.stdout.reconfigure(encoding="utf-8")
with contextlib.redirect_stdout(io.StringIO()):
    import study_filters as S
ref = S.R["SMA150 + 3 dagar (referens)"][0]
for lab, fam, vi in (("Faber 10 mån", "Faber 10 mån (8/10/12)", 1), ("Faber 10 mån ± 2 %", "Faber 10 mån ± 2/5 % band", 0)):
    print(lab)
    for c in sorted({c for c, _ in ref}):
        idx = [i for i, (cc, _) in enumerate(ref) if cc == c]
        L = S.R[fam][vi]
        d = [L[i][1]["sh"] - ref[i][1]["sh"] for i in idx]; dd = [L[i][1]["dd"] - ref[i][1]["dd"] for i in idx]
        print(f"  {c:15} n={len(idx):3}  Sharpe-diff median {statistics.median(d):+.3f}  slår {sum(x>0 for x in d)/len(d)*100:3.0f} %  fall-diff median {statistics.median(dd)*100:+.0f} p.e.")
D = [r for r in S.U if r[0] == "Kryptor"]
